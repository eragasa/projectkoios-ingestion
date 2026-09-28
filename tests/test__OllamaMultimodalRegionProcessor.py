from __future__ import annotations

import base64
import hashlib
import json
import threading
import zlib
from dataclasses import FrozenInstanceError, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from projectkoios.ingestion import (
    LoopbackOllamaHttpTransport,
    OllamaHttpResponse,
    OllamaMultimodalConfiguration,
    OllamaMultimodalConfigurationError,
    OllamaMultimodalDeterminism,
    OllamaMultimodalEvidenceStatus,
    OllamaMultimodalFailureKind,
    OllamaMultimodalLimits,
    OllamaMultimodalRegionProcessor,
    OllamaMultimodalRequest,
    OllamaMultimodalResult,
    OllamaMultimodalResultStatus,
    OllamaMultimodalSelection,
    OllamaMultimodalSelectionStatus,
    OllamaMultimodalWarning,
    OllamaRequestOptions,
    OllamaTransportError,
    OllamaTransportFailureKind,
    RegionRenderConfiguration,
    RenderedRegion,
    SourceDocument,
    build_ollama_multimodal_cache_key,
    normalize_ollama_endpoint,
    serialize_contract,
)

_DIGEST = "a" * 64
_MODEL = "fixture-vision:1"
_VERSION = "0.12.3"


def _png(fill: int = 1, width: int = 2, height: int = 1) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload).to_bytes(4, "big")
        return len(payload).to_bytes(4, "big") + kind + payload + checksum

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )
    row = b"\x00" + bytes((fill, fill, fill)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def _region(page_index: int = 0, fill: int = 1) -> RenderedRegion:
    source = SourceDocument.from_bytes(
        f"pdf-{page_index}-{fill}".encode(),
        source_id=f"source:{page_index}:{fill}",
        media_type="application/pdf",
        locator=f"memory://fixture-{page_index}-{fill}.pdf",
    )
    return RenderedRegion.create(
        source=source,
        page_index=page_index,
        printed_page_label=str(page_index + 1),
        source_bounding_box=(10.0, 20.0, 12.0, 21.0),
        effective_source_bounding_box=(10.0, 20.0, 12.0, 21.0),
        pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 10.0, 20.0),
        page_rotation_degrees=0,
        selection_was_full_page=False,
        configuration=RegionRenderConfiguration(resolution_dpi=72),
        content=_png(fill),
        width_pixels=2,
        height_pixels=1,
        processor_name="fixture-renderer",
        processor_version="1",
        backend_name="fixture-pdf",
        backend_version="1",
    )


def _request(count: int = 1) -> OllamaMultimodalRequest:
    return OllamaMultimodalRequest.create(
        tuple(
            OllamaMultimodalSelection.from_rendered_region(
                _region(index, index + 1)
            )
            for index in range(count)
        )
    )


def _json_response(value: object, status: int = 200) -> OllamaHttpResponse:
    return OllamaHttpResponse(
        status_code=status,
        content_type="application/json",
        body=json.dumps(value, separators=(",", ":")).encode(),
    )


def _structured_output(
    request: OllamaMultimodalRequest,
    *,
    item_count: int | None = None,
    extra_item_field: bool = False,
    text: str = "visible text",
) -> str:
    count = len(request.selections) if item_count is None else item_count
    items: list[dict[str, Any]] = []
    for index, selection in enumerate(request.selections[:count]):
        item: dict[str, Any] = {
            "index": index,
            "selection_id": selection.selection_id,
            "text": f"{text} {index}",
            "warnings": (["unclear glyph"] if index == 0 else []),
        }
        if extra_item_field:
            item["confidence"] = 1.0
        items.append(item)
    return json.dumps(
        {
            "schema_version": 1,
            "task": "page_region_transcription",
            "items": items,
        },
        separators=(",", ":"),
    )


def _chat_response(content: str, **extra: object) -> OllamaHttpResponse:
    value = {
        "model": _MODEL,
        "created_at": "2026-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
        "total_duration": 10,
        "eval_count": 2,
        **extra,
    }
    return _json_response(value)


class FakeTransport:
    def __init__(
        self,
        request: OllamaMultimodalRequest,
        *,
        digest: str = _DIGEST,
        postflight_digest: str | None = None,
        model_present: bool = True,
        version: str = _VERSION,
        version_response: OllamaHttpResponse | None = None,
        capabilities: tuple[str, ...] = ("completion", "vision"),
        chat_response: OllamaHttpResponse | None = None,
        fail_path: str | None = None,
        fail_kind: OllamaTransportFailureKind = (
            OllamaTransportFailureKind.TIMEOUT
        ),
    ) -> None:
        self.expected_request = request
        self.digest = digest
        self.postflight_digest = postflight_digest
        self.model_present = model_present
        self.version = version
        self.version_response = version_response
        self.capabilities = capabilities
        self.tags_calls = 0
        self.chat_response = chat_response
        self.fail_path = fail_path
        self.fail_kind = fail_kind
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        *,
        endpoint: str,
        method: str,
        path: str,
        body: bytes | None,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_response_bytes: int,
    ) -> OllamaHttpResponse:
        self.calls.append(
            {
                "endpoint": endpoint,
                "method": method,
                "path": path,
                "body": body,
                "connect_timeout_seconds": connect_timeout_seconds,
                "read_timeout_seconds": read_timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        if path == self.fail_path:
            raise OllamaTransportError(self.fail_kind, "injected failure")
        if path == "/api/version":
            response = self.version_response or _json_response(
                {"version": self.version}
            )
        elif path == "/api/tags":
            self.tags_calls += 1
            digest = (
                self.postflight_digest
                if self.tags_calls > 1 and self.postflight_digest is not None
                else self.digest
            )
            models = (
                [
                    {
                        "name": _MODEL,
                        "model": _MODEL,
                        "digest": digest,
                        "modified_at": "ignored",
                        "size": 1,
                        "details": {},
                    }
                ]
                if self.model_present
                else []
            )
            response = _json_response({"models": models})
        elif path == "/api/show":
            response = _json_response(
                {
                    "capabilities": list(self.capabilities),
                    "details": {},
                    "model_info": {},
                }
            )
        elif path == "/api/chat":
            response = self.chat_response or _chat_response(
                _structured_output(self.expected_request)
            )
        else:
            raise AssertionError(path)
        if len(response.body) > max_response_bytes:
            return response
        return response


def _assert_failed_complete_coverage(
    result: OllamaMultimodalResult,
    request: OllamaMultimodalRequest,
) -> None:
    assert result.status is OllamaMultimodalResultStatus.FAILED
    assert result.cacheable is False
    assert len(result.selection_results) == len(request.selections)
    assert all(
        item.status is OllamaMultimodalSelectionStatus.FAILED
        and item.failure is not None
        and item.proposal is None
        for item in result.selection_results
    )


def _processor(
    request: OllamaMultimodalRequest,
    *,
    transport: FakeTransport | None = None,
    digest: str = _DIGEST,
    limits: OllamaMultimodalLimits | None = None,
    options: OllamaRequestOptions | None = None,
) -> tuple[OllamaMultimodalRegionProcessor, FakeTransport]:
    actual_transport = transport or FakeTransport(request)
    processor = OllamaMultimodalRegionProcessor(
        configuration=OllamaMultimodalConfiguration(
            endpoint="http://127.0.0.1:11434/",
            model_name=_MODEL,
            expected_model_digest=digest,
            expected_ollama_version=_VERSION,
            limits=limits or OllamaMultimodalLimits(),
            options=options or OllamaRequestOptions(),
            connect_timeout_seconds=2.5,
            read_timeout_seconds=9.5,
        ),
        transport=actual_transport,
    )
    return processor, actual_transport


def test__successful_complete_proposals_preserve_order_and_provenance() -> None:
    request = _request(2)
    processor, transport = _processor(request)

    result = processor.process(request)

    assert result.status is OllamaMultimodalResultStatus.COMPLETE
    assert result.evidence_status is (
        OllamaMultimodalEvidenceStatus.AUTOMATED_UNREVIEWED
    )
    assert result.determinism is OllamaMultimodalDeterminism.NONDETERMINISTIC
    assert result.cacheable is True
    assert [call["path"] for call in transport.calls] == [
        "/api/version",
        "/api/tags",
        "/api/show",
        "/api/chat",
        "/api/tags",
    ]
    assert tuple(
        item.selection_id for item in result.selection_results
    ) == tuple(item.selection_id for item in request.selections)
    for source, item in zip(
        request.selections, result.selection_results, strict=True
    ):
        assert item.status is OllamaMultimodalSelectionStatus.PROPOSED
        assert item.source_id == source.source_id
        assert item.source_blob_id == source.source_blob_id
        assert item.source_content_hash == source.source_content_hash
        assert item.page_index == source.page_index
        assert item.region_id == source.region_id
        assert item.png_sha256 == source.png_sha256
        assert item.png_byte_length == source.png_byte_length
        assert item.proposal is not None
        assert (
            item.proposal.text_sha256
            == hashlib.sha256(item.proposal.text.encode()).hexdigest()
        )
    assert result.raw_response is not None
    assert result.raw_response.assistant_content_sha256 is not None
    assert result.model_verification is not None
    assert result.model_verification.preflight_observed_digest == _DIGEST
    assert result.model_verification.postflight_observed_digest == _DIGEST
    assert result.model_verification.limitation == (
        "non_atomic_tag_to_chat_binding"
    )
    assert serialize_contract(result) == serialize_contract(result)


def test__chat_binds_exact_images_prompt_schema_and_options() -> None:
    request = _request(2)
    options = OllamaRequestOptions(
        temperature=0.2, seed=42, context_tokens=4096, output_tokens=512
    )
    processor, transport = _processor(request, options=options)

    processor.process(request)

    chat_call = next(
        call for call in transport.calls if call["path"] == "/api/chat"
    )
    chat_body = chat_call["body"]
    assert isinstance(chat_body, bytes)
    payload = json.loads(chat_body)
    assert payload["model"] == _MODEL
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["keep_alive"] == "0"
    assert "tools" not in payload
    assert payload["format"]["additionalProperties"] is False
    assert payload["options"] == {
        "temperature": 0.2,
        "seed": 42,
        "num_ctx": 4096,
        "num_predict": 512,
    }
    message = payload["messages"][0]
    assert message["content"] == request.prompt.text
    assert message["images"] == [
        base64.b64encode(item.rendered_region.content).decode("ascii")
        for item in request.selections
    ]
    assert chat_call["endpoint"] == "http://127.0.0.1:11434"
    assert chat_call["connect_timeout_seconds"] == 2.5
    assert chat_call["read_timeout_seconds"] == 9.5


@pytest.mark.parametrize(
    ("digest", "capabilities", "kind"),
    [
        ("b" * 64, ("completion", "vision"), "model_digest_mismatch"),
        (_DIGEST, ("completion",), "model_capability_mismatch"),
    ],
)
def test__model_mismatch_fails_before_chat(
    digest: str, capabilities: tuple[str, ...], kind: str
) -> None:
    request = _request()
    transport = FakeTransport(request, digest=digest, capabilities=capabilities)
    processor, _ = _processor(request, transport=transport)

    result = processor.process(request)

    assert result.status is OllamaMultimodalResultStatus.FAILED
    assert result.cacheable is False
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind.value == kind
    assert "/api/chat" not in [call["path"] for call in transport.calls]


def test__missing_model_fails_before_show_or_chat() -> None:
    request = _request()
    transport = FakeTransport(request, model_present=False)
    processor, _ = _processor(request, transport=transport)

    result = processor.process(request)

    assert [call["path"] for call in transport.calls] == [
        "/api/version",
        "/api/tags",
    ]
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MODEL_MISSING
    )


def test__metadata_json_strictness_fails_before_model_or_chat() -> None:
    request = _request(2)
    duplicate = OllamaHttpResponse(
        200,
        "application/json",
        b'{"version":"0.12.3","version":"0.12.3"}',
    )
    transport = FakeTransport(request, version_response=duplicate)
    processor, _ = _processor(request, transport=transport)

    result = processor.process(request)

    assert [call["path"] for call in transport.calls] == ["/api/version"]
    _assert_failed_complete_coverage(result, request)
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MALFORMED_RESPONSE
    )


def test__runtime_version_mismatch_fails_before_model_or_chat() -> None:
    request = _request()
    transport = FakeTransport(request, version="0.12.4")
    processor, _ = _processor(request, transport=transport)

    result = processor.process(request)

    assert [call["path"] for call in transport.calls] == ["/api/version"]
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.BACKEND_VERSION_MISMATCH
    )
    assert result.cacheable is False


def test__postflight_digest_change_discards_valid_chat_output() -> None:
    request = _request()
    transport = FakeTransport(request, postflight_digest="b" * 64)
    processor, _ = _processor(request, transport=transport)

    result = processor.process(request)

    assert [call["path"] for call in transport.calls][-2:] == [
        "/api/chat",
        "/api/tags",
    ]
    assert result.status is OllamaMultimodalResultStatus.FAILED
    assert result.cacheable is False
    assert result.model_verification is None
    assert result.raw_response is not None
    assert result.selection_results[0].proposal is None
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MODEL_DIGEST_MISMATCH
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:11434",
        "http://192.168.1.2:11434",
        "http://example.test:11434",
        "http://user:secret@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
    ],
)
def test__nonlocal_or_unsafe_endpoint_is_rejected(endpoint: str) -> None:
    with pytest.raises(OllamaMultimodalConfigurationError):
        OllamaMultimodalConfiguration(
            endpoint=endpoint,
            model_name=_MODEL,
            expected_model_digest=_DIGEST,
            expected_ollama_version=_VERSION,
        )


def test__endpoint_normalization_is_privacy_safe() -> None:
    assert normalize_ollama_endpoint("http://[::1]:11434/") == (
        "http://[::1]:11434"
    )
    assert (
        normalize_ollama_endpoint("http://LOCALHOST") == "http://localhost:80"
    )


@pytest.mark.parametrize(
    ("path", "kind", "expected"),
    [
        ("/api/tags", OllamaTransportFailureKind.TIMEOUT, "timeout"),
        ("/api/chat", OllamaTransportFailureKind.TIMEOUT, "timeout"),
        (
            "/api/chat",
            OllamaTransportFailureKind.RESPONSE_LIMIT,
            "response_limit",
        ),
        (
            "/api/chat",
            OllamaTransportFailureKind.NETWORK,
            "transport_error",
        ),
    ],
)
def test__transport_failures_produce_complete_noncacheable_coverage(
    path: str,
    kind: OllamaTransportFailureKind,
    expected: str,
) -> None:
    request = _request(2)
    transport = FakeTransport(request, fail_path=path, fail_kind=kind)
    processor, _ = _processor(request, transport=transport)

    result = processor.process(request)

    assert result.cacheable is False
    assert len(result.selection_results) == 2
    assert all(item.failure is not None for item in result.selection_results)
    assert {
        item.failure.kind.value
        for item in result.selection_results
        if item.failure is not None
    } == {expected}


@pytest.mark.parametrize(
    "chat_response",
    [
        OllamaHttpResponse(200, "text/plain", b"{}"),
        _json_response(
            {
                "model": _MODEL,
                "created_at": "now",
                "message": {"role": "assistant", "content": "{}"},
                "done": True,
                "done_reason": "stop",
                "unexpected": True,
            }
        ),
        _json_response({"not": "a chat envelope"}),
        _json_response(
            {
                "model": _MODEL,
                "created_at": "now",
                "message": {
                    "role": "assistant",
                    "content": "{}",
                    "tool_calls": [],
                },
                "done": True,
                "done_reason": "stop",
            }
        ),
    ],
)
def test__malformed_or_extra_chat_response_fields_fail_closed(
    chat_response: OllamaHttpResponse,
) -> None:
    request = _request()
    transport = FakeTransport(request, chat_response=chat_response)
    processor, _ = _processor(request, transport=transport)

    result = processor.process(request)

    assert result.status is OllamaMultimodalResultStatus.FAILED
    assert result.cacheable is False
    assert result.selection_results[0].failure is not None
    assert result.raw_response is not None


def test__partial_output_fails_every_selection_without_partial_proposals() -> (
    None
):
    request = _request(2)
    chat = _chat_response(_structured_output(request, item_count=1))
    processor, _ = _processor(
        request, transport=FakeTransport(request, chat_response=chat)
    )

    result = processor.process(request)

    assert result.status is OllamaMultimodalResultStatus.FAILED
    assert all(item.proposal is None for item in result.selection_results)
    assert {
        item.failure.kind for item in result.selection_results if item.failure
    } == {OllamaMultimodalFailureKind.INCOMPLETE_COVERAGE}


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", True), ("index", False)],
)
def test__json_booleans_do_not_satisfy_integer_schema_fields(
    field: str, value: bool
) -> None:
    request = _request()
    output = json.loads(_structured_output(request))
    if field == "schema_version":
        output[field] = value
    else:
        output["items"][0][field] = value
    chat = _chat_response(json.dumps(output, separators=(",", ":")))
    processor, _ = _processor(
        request, transport=FakeTransport(request, chat_response=chat)
    )

    result = processor.process(request)

    _assert_failed_complete_coverage(result, request)
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MALFORMED_RESPONSE
    )


def test__extra_structured_output_field_is_rejected() -> None:
    request = _request()
    chat = _chat_response(_structured_output(request, extra_item_field=True))
    processor, _ = _processor(
        request, transport=FakeTransport(request, chat_response=chat)
    )

    result = processor.process(request)

    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MALFORMED_RESPONSE
    )


def test__deep_json_is_a_failed_result_not_an_uncaught_recursion() -> None:
    request = _request(2)
    payload = ('{"nested":' + "[" * 40 + "0" + "]" * 40 + "}").encode()
    chat = OllamaHttpResponse(200, "application/json", payload)
    processor, _ = _processor(
        request, transport=FakeTransport(request, chat_response=chat)
    )

    result = processor.process(request)

    _assert_failed_complete_coverage(result, request)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test__non_rfc_json_constants_are_rejected(constant: str) -> None:
    request = _request()
    selection_id = json.dumps(request.selections[0].selection_id)
    content = (
        '{"schema_version":1,"task":"page_region_transcription",'
        f'"items":[{{"index":0,"selection_id":{selection_id},'
        f'"text":{constant},"warnings":[]}}]}}'
    )
    processor, _ = _processor(
        request,
        transport=FakeTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.process(request)

    _assert_failed_complete_coverage(result, request)


@pytest.mark.parametrize("mutation", ["nul_warning", "surrogate_text"])
def test__invalid_untrusted_unicode_or_controls_fail_closed(
    mutation: str,
) -> None:
    request = _request(2)
    output = json.loads(_structured_output(request))
    if mutation == "nul_warning":
        output["items"][0]["warnings"] = ["bad\x00warning"]
    else:
        output["items"][0]["text"] = "bad\ud800text"
    content = json.dumps(output, separators=(",", ":"))
    processor, _ = _processor(
        request,
        transport=FakeTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.process(request)

    _assert_failed_complete_coverage(result, request)


def test__duplicate_json_fields_are_rejected() -> None:
    request = _request()
    selection_id = json.dumps(request.selections[0].selection_id)
    content = (
        '{"schema_version":1,"schema_version":1,'
        '"task":"page_region_transcription","items":['
        f'{{"index":0,"selection_id":{selection_id},'
        '"text":"text","warnings":[]}]}'
    )
    processor, _ = _processor(
        request,
        transport=FakeTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.process(request)

    _assert_failed_complete_coverage(result, request)


def test__json_string_bytes_have_an_independent_hard_bound() -> None:
    request = _request(2)
    content = (
        '{"schema_version":1,"task":"page_region_transcription",'
        '"items":[],"extra":"' + "x" * 4_000_001 + '"}'
    )
    processor, _ = _processor(
        request,
        transport=FakeTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.process(request)

    _assert_failed_complete_coverage(result, request)


def test__json_item_count_is_bounded_before_schema_validation() -> None:
    request = _request()
    content = (
        '{"schema_version":1,"task":"page_region_transcription",'
        '"items":[],"extra":[' + ",".join("0" for _ in range(100_001)) + "]}"
    )
    processor, _ = _processor(
        request,
        transport=FakeTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.process(request)

    _assert_failed_complete_coverage(result, request)


def test__configured_input_bound_fails_before_metadata() -> None:
    request = _request()
    image_size = request.selections[0].png_byte_length
    limits = OllamaMultimodalLimits(
        max_image_bytes=image_size - 1,
        max_total_image_bytes=image_size - 1,
    )
    processor, transport = _processor(request, limits=limits)

    result = processor.process(request)

    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.INPUT_LIMIT
    )
    assert transport.calls == []


def test__configured_request_and_output_bounds_fail_closed() -> None:
    request = _request()
    request_limits = OllamaMultimodalLimits(max_request_bytes=1)
    processor, transport = _processor(request, limits=request_limits)
    result = processor.process(request)
    assert [call["path"] for call in transport.calls] == [
        "/api/version",
        "/api/tags",
        "/api/show",
    ]
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.INPUT_LIMIT
    )

    output_limits = OllamaMultimodalLimits(
        max_output_bytes=10,
        max_output_bytes_per_selection=10,
    )
    processor, _ = _processor(request, limits=output_limits)
    result = processor.process(request)
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.OUTPUT_LIMIT
    )


def test__oversized_transport_response_is_defensively_rejected() -> None:
    request = _request()
    limits = OllamaMultimodalLimits(
        max_response_bytes=100,
        max_output_bytes=100,
        max_output_bytes_per_selection=100,
    )
    huge = OllamaHttpResponse(200, "application/json", b"x" * 101)
    processor, _ = _processor(
        request,
        limits=limits,
        transport=FakeTransport(request, chat_response=huge),
    )

    result = processor.process(request)

    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.RESPONSE_LIMIT
    )


def test__stale_evidence_fails_before_transport() -> None:
    request = _request()
    region = request.selections[0].rendered_region
    object.__setattr__(region, "content", region.content + b"stale")
    processor, transport = _processor(request)

    result = processor.process(request)

    assert transport.calls == []
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.STALE_EVIDENCE
    )


def test__identities_and_cache_key_invalidate_on_every_material_input() -> None:
    first_request = _request()
    changed_request = OllamaMultimodalRequest.create(
        (OllamaMultimodalSelection.from_rendered_region(_region(0, 9)),)
    )
    first, _ = _processor(first_request)
    changed_model, _ = _processor(first_request, digest="b" * 64)
    changed_options, _ = _processor(
        first_request, options=OllamaRequestOptions(seed=1)
    )

    first_key = build_ollama_multimodal_cache_key(
        first_request, first.identity()
    )
    assert first_key != build_ollama_multimodal_cache_key(
        changed_request, first.identity()
    )
    assert first_key != build_ollama_multimodal_cache_key(
        first_request, changed_model.identity()
    )
    assert first_key != build_ollama_multimodal_cache_key(
        first_request, changed_options.identity()
    )
    assert first.identity().expected_model_digest == _DIGEST
    assert first.identity().endpoint == "http://127.0.0.1:11434"
    assert first.identity().required_capabilities == ("vision",)
    assert (
        first_request.prompt.rendered_sha256
        != changed_request.prompt.rendered_sha256
    )
    with pytest.raises(FrozenInstanceError):
        first_request.request_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="identity"):
        replace(first_request, request_id="bad")


class _RedirectHandler(BaseHTTPRequestHandler):
    requested_paths: list[str] = []

    def do_GET(self) -> None:  # noqa: N802
        self.requested_paths.append(self.path)
        self.send_response(302)
        self.send_header("Location", "http://example.com/forbidden")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def test__direct_construction_tampering_is_rejected() -> None:
    request = _request(2)
    processor, _ = _processor(request)
    result = processor.process(request)
    assert result.model_verification is not None
    assert result.raw_response is not None

    with pytest.raises(ValueError, match="configuration"):
        replace(processor.identity(), endpoint="http://localhost:11434")
    with pytest.raises(ValueError, match="observed model digests"):
        replace(
            result.model_verification,
            postflight_observed_digest="b" * 64,
        )
    with pytest.raises(ValueError, match="stage and path"):
        replace(result.metadata_responses[0], path="/api/tags")
    with pytest.raises(ValueError, match="provenance identity"):
        replace(result.selection_results[0], source_id="source:tampered")
    with pytest.raises(ValueError, match="coverage"):
        replace(
            result,
            selection_results=tuple(reversed(result.selection_results)),
        )
    with pytest.raises(ValueError, match="request identity"):
        replace(
            result,
            request_id="ollama-multimodal-request:sha256:" + "0" * 64,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        replace(result.raw_response, http_body_sha256="bad")
    with pytest.raises(ValueError, match="cacheable"):
        replace(result, cacheable=False)
    with pytest.raises(ValueError, match="empty"):
        OllamaMultimodalWarning(code="", message="bad")

    failed_transport = FakeTransport(request, digest="b" * 64)
    failed_processor, _ = _processor(request, transport=failed_transport)
    failure = failed_processor.process(request).selection_results[0].failure
    assert failure is not None
    with pytest.raises(TypeError, match="boolean"):
        replace(failure, retryable=1)  # type: ignore[arg-type]


def test__production_transport_ignores_proxy_and_does_not_follow_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("HTTP_PROXY", "http://192.0.2.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://192.0.2.1:9")
    _RedirectHandler.requested_paths = []
    try:
        response = LoopbackOllamaHttpTransport().request(
            endpoint=f"http://127.0.0.1:{server.server_port}",
            method="GET",
            path="/api/tags",
            body=None,
            connect_timeout_seconds=1.0,
            read_timeout_seconds=1.0,
            max_response_bytes=100,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert response.status_code == 302
    assert _RedirectHandler.requested_paths == ["/api/tags"]
