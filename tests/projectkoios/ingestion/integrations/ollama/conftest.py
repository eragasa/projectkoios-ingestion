from __future__ import annotations

import json
import zlib
from typing import Any

from projectkoios.ingestion import (
    RegionRenderConfiguration,
    RenderedRegion,
    SourceDocument,
)
from projectkoios.ingestion.integrations.ollama.base import (
    OllamaHttpResponse,
    OllamaRequestOptions,
    OllamaTransport,
    OllamaTransportError,
    OllamaTransportFailureKind,
)
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalConfiguration,
    OllamaMultimodalLimits,
    OllamaMultimodalResultStatus,
    OllamaMultimodalSelection,
    OllamaMultimodalSelectionStatus,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region import (  # noqa: E501
    base as region_base,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region import (  # noqa: E501
    request as region_request,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region import (  # noqa: E501
    result as region_result,
)

OllamaMultimodalRegionProcessor = region_base.OllamaMultimodalRegionProcessor
OllamaMultimodalRegionProcessingRequest = (
    region_request.OllamaMultimodalRegionProcessingRequest
)
OllamaMultimodalRegionProcessingResult = (
    region_result.OllamaMultimodalRegionProcessingResult
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


def _request(count: int = 1) -> OllamaMultimodalRegionProcessingRequest:
    return OllamaMultimodalRegionProcessingRequest.create(
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
    request: OllamaMultimodalRegionProcessingRequest,
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


class MockTransport(OllamaTransport):
    def __init__(
        self,
        request: OllamaMultimodalRegionProcessingRequest,
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
    result: OllamaMultimodalRegionProcessingResult,
    request: OllamaMultimodalRegionProcessingRequest,
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
    request: OllamaMultimodalRegionProcessingRequest,
    *,
    transport: MockTransport | None = None,
    digest: str = _DIGEST,
    limits: OllamaMultimodalLimits | None = None,
    options: OllamaRequestOptions | None = None,
) -> tuple[OllamaMultimodalRegionProcessor, MockTransport]:
    actual_transport = transport or MockTransport(request)
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
