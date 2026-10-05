"""OCRReconciliationWarning reconciliation domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.models import Metadata, WarningSeverity
from projectkoios.ingestion.reconciliation import _identity as identity
from projectkoios.ingestion.reconciliation import _primitives as primitives


@dataclass(frozen=True)
class OCRReconciliationWarning(AbstractImmutableDataObject):
    warning_id: str
    code: str
    severity: WarningSeverity
    message: str
    object_ids: tuple[str, ...]
    evidence: Metadata = ()

    @classmethod
    def create(
        cls,
        *,
        code: str,
        severity: WarningSeverity,
        message: str,
        object_ids: tuple[str, ...],
        evidence: Metadata = (),
    ) -> OCRReconciliationWarning:
        primitives._bounded_string("warning code", code)
        if not isinstance(severity, WarningSeverity):
            raise ValueError("warning severity is unsupported")
        primitives._bounded_text("warning message", message, nonempty=True)
        primitives._require_unique_strings(
            "warning object IDs", object_ids, True
        )
        primitives._validate_metadata(evidence)
        warning_id = identity._warning_id(
            code, severity, message, object_ids, evidence
        )
        return cls(
            warning_id=warning_id,
            code=code,
            severity=severity,
            message=message,
            object_ids=object_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        primitives._bounded_string("warning ID", self.warning_id)
        primitives._bounded_string("warning code", self.code)
        if not isinstance(self.severity, WarningSeverity):
            raise ValueError("warning severity is unsupported")
        primitives._bounded_text("warning message", self.message, nonempty=True)
        primitives._require_unique_strings(
            "warning object IDs", self.object_ids, True
        )
        primitives._validate_metadata(self.evidence)
        expected = identity._warning_id(
            self.code,
            self.severity,
            self.message,
            self.object_ids,
            self.evidence,
        )
        if self.warning_id != expected:
            raise ValueError("reconciliation warning ID is inconsistent")
