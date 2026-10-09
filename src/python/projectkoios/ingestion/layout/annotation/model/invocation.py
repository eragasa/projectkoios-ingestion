"""Exact request and raw-response byte evidence for one model invocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.model.prompt import (
    MAX_LAYOUT_MODEL_PROMPT_BYTES,
)
from projectkoios.ingestion.layout.annotation.model.request import (
    LayoutAnnotationModelRequest,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash

MAX_LAYOUT_MODEL_REQUEST_DOCUMENT_BYTES = MAX_LAYOUT_MODEL_PROMPT_BYTES * 2


class LayoutAnnotationModelInvocationStatus(StrEnum):
    """Closed execution outcome for one provider invocation."""

    COMPLETE = "complete"
    FAILED = "failed"


class LayoutAnnotationModelInvocationFailureKind(StrEnum):
    """Provider-neutral failure taxonomy without retry policy."""

    INPUT_UNAVAILABLE = "input_unavailable"
    RESOURCE_MISMATCH = "resource_mismatch"
    REQUEST_LIMIT = "request_limit"
    RESPONSE_LIMIT = "response_limit"
    TRANSPORT = "transport"
    PROVIDER_PROTOCOL = "provider_protocol"


@dataclass(frozen=True, slots=True)
class LayoutAnnotationModelInvocationResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Retain an exact request document and exact raw response bytes."""

    CONTRACT_NAME: ClassVar[str] = "layout-annotation-model-invocation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request: LayoutAnnotationModelRequest
    status: LayoutAnnotationModelInvocationStatus
    request_document_bytes: bytes
    raw_response_bytes: bytes | None
    failure_kind: LayoutAnnotationModelInvocationFailureKind | None
    failure_code: str | None
    request_document_sha256: SHA256Hash = field(init=False)
    raw_response_sha256: SHA256Hash | None = field(init=False)
    invocation_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not LayoutAnnotationModelRequest:
            raise TypeError("request must be LayoutAnnotationModelRequest")
        if not isinstance(self.status, LayoutAnnotationModelInvocationStatus):
            raise TypeError(
                "status must be LayoutAnnotationModelInvocationStatus"
            )
        if not isinstance(self.request_document_bytes, bytes):
            raise TypeError("request_document_bytes must be bytes")
        request_bytes = self.request_document_bytes
        if (
            not request_bytes
            or len(request_bytes) > MAX_LAYOUT_MODEL_REQUEST_DOCUMENT_BYTES
        ):
            raise ValueError("model request document has an invalid length")
        if request_bytes != self.request.document_bytes():
            raise ValueError("model request document differs from the request")
        request_sha256 = SHA256Hash(
            SHA256Fingerprinter.fingerprint(content=request_bytes)
        )
        response_sha256: SHA256Hash | None = None
        if self.raw_response_bytes is not None:
            if not isinstance(self.raw_response_bytes, bytes):
                raise TypeError("raw_response_bytes must be bytes or None")
            if (
                len(self.raw_response_bytes)
                > self.request.configuration.maximum_response_bytes
            ):
                raise ValueError("raw response exceeds its request-bound limit")
            response_sha256 = SHA256Hash(
                SHA256Fingerprinter.fingerprint(content=self.raw_response_bytes)
            )
        if self.status is LayoutAnnotationModelInvocationStatus.COMPLETE:
            if self.raw_response_bytes is None:
                raise ValueError("complete invocation requires a raw response")
            if self.failure_kind is not None or self.failure_code is not None:
                raise ValueError("complete invocation cannot carry a failure")
        else:
            if not isinstance(
                self.failure_kind,
                LayoutAnnotationModelInvocationFailureKind,
            ):
                raise ValueError("failed invocation requires a failure kind")
            LayoutValueValidation.require_text(
                "failure_code", self.failure_code
            )
        object.__setattr__(self, "request_document_sha256", request_sha256)
        object.__setattr__(self, "raw_response_sha256", response_sha256)
        object.__setattr__(
            self,
            "invocation_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.request.request_id,
                self.status,
                request_sha256,
                len(request_bytes),
                response_sha256,
                self.raw_response_byte_length,
                self.failure_kind,
                self.failure_code,
            ),
        )

    @property
    def request_document_byte_length(self) -> int:
        """Return the exact canonical request-document length."""
        return len(self.request_document_bytes)

    @property
    def raw_response_byte_length(self) -> int | None:
        """Return the exact raw response length when response bytes exist."""
        if self.raw_response_bytes is None:
            return None
        return len(self.raw_response_bytes)
