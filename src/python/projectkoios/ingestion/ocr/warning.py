"""OCRWarning OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.models import Metadata, WarningSeverity
from projectkoios.ingestion.ocr.identity import derivation as identity
from projectkoios.ingestion.ocr.limit.definition import (
    _MAX_WARNING_MESSAGE_CHARACTERS,
)
from projectkoios.ingestion.ocr.validation import value as primitives


@dataclass(frozen=True)
class OCRWarning(AbstractImmutableDataObject):
    """A stable selection-local warning reported by an OCR adapter."""

    warning_id: str
    selection_id: str
    code: str
    severity: WarningSeverity
    message: str
    evidence: Metadata = ()

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        code: str,
        severity: WarningSeverity,
        message: str,
        evidence: Metadata = (),
    ) -> OCRWarning:
        primitives._hard_bounded_string(
            "selection_id", selection_id, nonempty=True
        )
        primitives._hard_bounded_string("warning code", code, nonempty=True)
        primitives._hard_bounded_string(
            "warning message",
            message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(severity, WarningSeverity):
            raise ValueError("OCR warning severity is unsupported")
        primitives._validate_metadata(evidence)
        return cls(
            warning_id=identity._ocr_warning_id(
                selection_id, code, severity, message, evidence
            ),
            selection_id=selection_id,
            code=code,
            severity=severity,
            message=message,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        primitives._hard_bounded_string(
            "selection_id", self.selection_id, nonempty=True
        )
        primitives._hard_bounded_string(
            "warning code", self.code, nonempty=True
        )
        primitives._hard_bounded_string(
            "warning message",
            self.message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        if not isinstance(self.severity, WarningSeverity):
            raise ValueError("OCR warning severity is unsupported")
        primitives._validate_metadata(self.evidence)
        expected = identity._ocr_warning_id(
            self.selection_id,
            self.code,
            self.severity,
            self.message,
            self.evidence,
        )
        if self.warning_id != expected:
            raise ValueError("OCR warning ID does not match its evidence")
