"""Exact request and raw-output evidence for local detector invocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.request import (  # noqa: E501
    CocoLayoutDetectorInvocationRequest,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


class CocoLayoutDetectorInvocationStatus(StrEnum):
    """Closed local detector execution outcomes."""

    COMPLETE = "complete"
    FAILED = "failed"


class CocoLayoutDetectorInvocationFailureKind(StrEnum):
    """Provider-neutral local detector failure taxonomy."""

    IMAGE_UNAVAILABLE = "image_unavailable"
    IMAGE_MISMATCH = "image_mismatch"
    RESOURCE_MISMATCH = "resource_mismatch"
    REQUEST_LIMIT = "request_limit"
    OUTPUT_LIMIT = "output_limit"
    RUNTIME = "runtime"
    PROVIDER_PROTOCOL = "provider_protocol"


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorInvocationResult(AbstractDataObjectActionResult):
    """Retain exact canonical request and exact raw detector output bytes."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-detector-invocation-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request: CocoLayoutDetectorInvocationRequest
    status: CocoLayoutDetectorInvocationStatus
    request_document_bytes: bytes
    raw_output_bytes: bytes | None
    elapsed_nanoseconds: int
    failure_kind: CocoLayoutDetectorInvocationFailureKind | None
    failure_code: str | None
    request_document_sha256: SHA256Hash = field(init=False)
    raw_output_sha256: SHA256Hash | None = field(init=False)
    invocation_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutDetectorInvocationRequest:
            raise TypeError(
                "request must be CocoLayoutDetectorInvocationRequest"
            )
        if not isinstance(self.status, CocoLayoutDetectorInvocationStatus):
            raise TypeError("status must be CocoLayoutDetectorInvocationStatus")
        if type(self.request_document_bytes) is not bytes:
            raise TypeError("request_document_bytes must be bytes")
        if self.request_document_bytes != self.request.document_bytes():
            raise ValueError("invocation request document differs from request")
        request_sha256 = SHA256Hash(
            SHA256Fingerprinter.fingerprint(content=self.request_document_bytes)
        )
        elapsed = LayoutValueValidation.require_nonnegative_integer(
            "elapsed_nanoseconds", self.elapsed_nanoseconds
        )
        output_sha256: SHA256Hash | None = None
        if self.raw_output_bytes is not None:
            if type(self.raw_output_bytes) is not bytes:
                raise TypeError("raw_output_bytes must be bytes or None")
            if len(self.raw_output_bytes) > self.request.maximum_output_bytes:
                raise ValueError(
                    "raw detector output exceeds its request bound"
                )
            output_sha256 = SHA256Hash(
                SHA256Fingerprinter.fingerprint(content=self.raw_output_bytes)
            )
        if self.status is CocoLayoutDetectorInvocationStatus.COMPLETE:
            if not self.raw_output_bytes:
                raise ValueError(
                    "complete detector invocation requires raw output bytes"
                )
            if self.failure_kind is not None or self.failure_code is not None:
                raise ValueError(
                    "complete detector invocation cannot carry a failure"
                )
        else:
            if self.raw_output_bytes is not None:
                raise ValueError(
                    "failed detector invocation cannot carry raw output"
                )
            if not isinstance(
                self.failure_kind,
                CocoLayoutDetectorInvocationFailureKind,
            ):
                raise ValueError(
                    "failed detector invocation requires a failure kind"
                )
            LayoutValueValidation.require_text(
                "failure_code", self.failure_code
            )
        object.__setattr__(self, "request_document_sha256", request_sha256)
        object.__setattr__(self, "raw_output_sha256", output_sha256)
        object.__setattr__(
            self,
            "invocation_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.request.request_id,
                self.status,
                request_sha256,
                len(self.request_document_bytes),
                output_sha256,
                self.raw_output_byte_length,
                elapsed,
                self.failure_kind,
                self.failure_code,
            ),
        )

    @property
    def raw_output_byte_length(self) -> int | None:
        """Return exact raw output length when output bytes exist."""
        if self.raw_output_bytes is None:
            return None
        return len(self.raw_output_bytes)
