"""OCRFailure OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.ocr import _identity as identity
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr._limits import _MAX_WARNING_MESSAGE_CHARACTERS
from projectkoios.ingestion.ocr.failure_kind import OCRFailureKind


@dataclass(frozen=True)
class OCRFailure(AbstractImmutableDataObject):
    """Typed evidence explaining a partial or failed OCR selection."""

    failure_id: str
    selection_id: str
    kind: OCRFailureKind
    message: str
    retryable: bool
    warning_ids: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        kind: OCRFailureKind,
        message: str,
        retryable: bool,
        warning_ids: tuple[str, ...],
    ) -> OCRFailure:
        primitives._hard_bounded_string(
            "selection_id", selection_id, nonempty=True
        )
        if not isinstance(kind, OCRFailureKind):
            raise ValueError("OCR failure kind is unsupported")
        primitives._hard_bounded_string(
            "failure message",
            message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(retryable, bool):
            raise ValueError("retryable must be a boolean")
        primitives._require_unique_strings(
            "warning_ids", warning_ids, required=True
        )
        return cls(
            failure_id=identity._ocr_failure_id(
                selection_id, kind, message, retryable, warning_ids
            ),
            selection_id=selection_id,
            kind=kind,
            message=message,
            retryable=retryable,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        primitives._hard_bounded_string(
            "selection_id", self.selection_id, nonempty=True
        )
        if not isinstance(self.kind, OCRFailureKind):
            raise ValueError("OCR failure kind is unsupported")
        primitives._hard_bounded_string(
            "failure message",
            self.message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(self.retryable, bool):
            raise ValueError("retryable must be a boolean")
        primitives._require_unique_strings(
            "warning_ids", self.warning_ids, required=True
        )
        expected = identity._ocr_failure_id(
            self.selection_id,
            self.kind,
            self.message,
            self.retryable,
            self.warning_ids,
        )
        if self.failure_id != expected:
            raise ValueError("OCR failure ID does not match its evidence")
