from __future__ import annotations

import base64
import json

import pytest
from conftest import (
    _DIGEST,
    _MODEL,
    MockTransport,
    _assert_failed_complete_coverage,
    _chat_response,
    _json_response,
    _processor,
    _request,
    _structured_output,
)
from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion import serialize_contract
from projectkoios.ingestion.integrations.ollama.base import (
    OllamaHttpResponse,
    OllamaRequestOptions,
    OllamaTransportFailureKind,
)
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalDeterminism,
    OllamaMultimodalEvidenceStatus,
    OllamaMultimodalFailureKind,
    OllamaMultimodalLimits,
    OllamaMultimodalResultStatus,
    OllamaMultimodalSelectionStatus,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.base import (  # noqa: E501
    OllamaMultimodalRegionProcessor,
)
from projectkoios.ingestion.sha256.verifier import SHA256Verifier


def test__ollama_multimodal_region_processor__is_an_actionizer() -> None:
    assert issubclass(OllamaMultimodalRegionProcessor, DataObjectActionizer)


def test__successful_complete_proposals_preserve_order_and_provenance() -> None:
    request = _request(2)
    processor, transport = _processor(request)

    result = processor.action(request=request)

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
        assert SHA256Verifier.verify(
            content=item.proposal.text.encode(),
            expected=item.proposal.text_sha256,
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

    processor.action(request=request)

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
    transport = MockTransport(request, digest=digest, capabilities=capabilities)
    processor, _ = _processor(request, transport=transport)

    result = processor.action(request=request)

    assert result.status is OllamaMultimodalResultStatus.FAILED
    assert result.cacheable is False
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind.value == kind
    assert "/api/chat" not in [call["path"] for call in transport.calls]


def test__missing_model_fails_before_show_or_chat() -> None:
    request = _request()
    transport = MockTransport(request, model_present=False)
    processor, _ = _processor(request, transport=transport)

    result = processor.action(request=request)

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
    transport = MockTransport(request, version_response=duplicate)
    processor, _ = _processor(request, transport=transport)

    result = processor.action(request=request)

    assert [call["path"] for call in transport.calls] == ["/api/version"]
    _assert_failed_complete_coverage(result, request)
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MALFORMED_RESPONSE
    )


def test__runtime_version_mismatch_fails_before_model_or_chat() -> None:
    request = _request()
    transport = MockTransport(request, version="0.12.4")
    processor, _ = _processor(request, transport=transport)

    result = processor.action(request=request)

    assert [call["path"] for call in transport.calls] == ["/api/version"]
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.BACKEND_VERSION_MISMATCH
    )
    assert result.cacheable is False


def test__postflight_digest_change_discards_valid_chat_output() -> None:
    request = _request()
    transport = MockTransport(request, postflight_digest="b" * 64)
    processor, _ = _processor(request, transport=transport)

    result = processor.action(request=request)

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
    transport = MockTransport(request, fail_path=path, fail_kind=kind)
    processor, _ = _processor(request, transport=transport)

    result = processor.action(request=request)

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
    transport = MockTransport(request, chat_response=chat_response)
    processor, _ = _processor(request, transport=transport)

    result = processor.action(request=request)

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
        request, transport=MockTransport(request, chat_response=chat)
    )

    result = processor.action(request=request)

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
        request, transport=MockTransport(request, chat_response=chat)
    )

    result = processor.action(request=request)

    _assert_failed_complete_coverage(result, request)
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MALFORMED_RESPONSE
    )


def test__extra_structured_output_field_is_rejected() -> None:
    request = _request()
    chat = _chat_response(_structured_output(request, extra_item_field=True))
    processor, _ = _processor(
        request, transport=MockTransport(request, chat_response=chat)
    )

    result = processor.action(request=request)

    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.MALFORMED_RESPONSE
    )


def test__deep_json_is_a_failed_result_not_an_uncaught_recursion() -> None:
    request = _request(2)
    payload = ('{"nested":' + "[" * 40 + "0" + "]" * 40 + "}").encode()
    chat = OllamaHttpResponse(200, "application/json", payload)
    processor, _ = _processor(
        request, transport=MockTransport(request, chat_response=chat)
    )

    result = processor.action(request=request)

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
        transport=MockTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.action(request=request)

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
        transport=MockTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.action(request=request)

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
        transport=MockTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.action(request=request)

    _assert_failed_complete_coverage(result, request)


def test__json_string_bytes_have_an_independent_hard_bound() -> None:
    request = _request(2)
    content = (
        '{"schema_version":1,"task":"page_region_transcription",'
        '"items":[],"extra":"' + "x" * 4_000_001 + '"}'
    )
    processor, _ = _processor(
        request,
        transport=MockTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.action(request=request)

    _assert_failed_complete_coverage(result, request)


def test__json_item_count_is_bounded_before_schema_validation() -> None:
    request = _request()
    content = (
        '{"schema_version":1,"task":"page_region_transcription",'
        '"items":[],"extra":[' + ",".join("0" for _ in range(100_001)) + "]}"
    )
    processor, _ = _processor(
        request,
        transport=MockTransport(request, chat_response=_chat_response(content)),
    )

    result = processor.action(request=request)

    _assert_failed_complete_coverage(result, request)


def test__configured_input_bound_fails_before_metadata() -> None:
    request = _request()
    image_size = request.selections[0].png_byte_length
    limits = OllamaMultimodalLimits(
        max_image_bytes=image_size - 1,
        max_total_image_bytes=image_size - 1,
    )
    processor, transport = _processor(request, limits=limits)

    result = processor.action(request=request)

    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.INPUT_LIMIT
    )
    assert transport.calls == []


def test__configured_request_and_output_bounds_fail_closed() -> None:
    request = _request()
    request_limits = OllamaMultimodalLimits(max_request_bytes=1)
    processor, transport = _processor(request, limits=request_limits)
    result = processor.action(request=request)
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
    result = processor.action(request=request)
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
        transport=MockTransport(request, chat_response=huge),
    )

    result = processor.action(request=request)

    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.RESPONSE_LIMIT
    )


def test__stale_evidence_fails_before_transport() -> None:
    request = _request()
    region = request.selections[0].rendered_region
    object.__setattr__(region, "content", region.content + b"stale")
    processor, transport = _processor(request)

    result = processor.action(request=request)

    assert transport.calls == []
    assert result.selection_results[0].failure is not None
    assert result.selection_results[0].failure.kind is (
        OllamaMultimodalFailureKind.STALE_EVIDENCE
    )
