"""Immutable recorded producer-audit evidence."""

from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.provenance.audit import (
    DERIVATION_AUDIT_CONTRACT_VERSION,
    DerivationAuditStatus,
)
from projectkoios.ingestion.reference.evidence.artifact import (
    ReferenceEvidenceArtifact,
)
from projectkoios.ingestion.reference.evidence.layer import (
    ReferenceEvidenceLayerCountInventory,
)
from projectkoios.ingestion.reference.evidence.lineage import (
    ReferenceEvidenceAuditArtifactIdentityInventory,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)

REFERENCE_EVIDENCE_DERIVATION_AUDIT_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.derivation-audit+json"
)


class ReferenceEvidenceAuditScope(StrEnum):
    """Exact authority scope of the recorded producer audit."""

    RECORDED_PRODUCER_DERIVATION_AUDIT = "recorded_producer_derivation_audit"


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceAudit:
    """Record an exact producer audit without claiming revalidation."""

    artifact: ReferenceEvidenceArtifact
    contract_version: str
    report_id: str
    status: DerivationAuditStatus
    scope: ReferenceEvidenceAuditScope
    independently_revalidated: bool
    processor_name: str
    processor_version: str
    audited_artifact_ids: ReferenceEvidenceAuditArtifactIdentityInventory
    audited_layer_counts: ReferenceEvidenceLayerCountInventory
    finding_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, ReferenceEvidenceArtifact):
            raise TypeError("audit artifact identity is required")
        if (
            self.artifact.media_type
            != REFERENCE_EVIDENCE_DERIVATION_AUDIT_MEDIA_TYPE
        ):
            raise ValueError("unsupported audit artifact media type")
        if self.contract_version != DERIVATION_AUDIT_CONTRACT_VERSION:
            raise ValueError("unsupported derivation-audit contract version")
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        requirements.require_text(
            self.report_id,
            "audit report_id",
        )
        if not isinstance(self.status, DerivationAuditStatus):
            raise TypeError("audit status is unsupported")
        if not isinstance(self.scope, ReferenceEvidenceAuditScope):
            raise TypeError("audit scope is unsupported")
        if self.independently_revalidated is not False:
            raise ValueError(
                "reference evidence cannot claim independent revalidation"
            )
        requirements.require_text(
            self.processor_name,
            "audit processor_name",
        )
        requirements.require_text(
            self.processor_version,
            "audit processor_version",
        )
        if not isinstance(
            self.audited_artifact_ids,
            ReferenceEvidenceAuditArtifactIdentityInventory,
        ):
            raise TypeError(
                "audit audited_artifact_ids must be a semantic inventory"
            )
        if not isinstance(
            self.audited_layer_counts,
            ReferenceEvidenceLayerCountInventory,
        ):
            raise TypeError(
                "audit audited_layer_counts must be a semantic inventory"
            )
        requirements.require_nonnegative_int(
            self.finding_count,
            "audit finding_count",
        )
