"""Aggregate immutable reference-evidence action result."""

from dataclasses import dataclass

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.reference.evidence.audit import (
    ReferenceEvidenceAudit,
)
from projectkoios.ingestion.reference.evidence.completeness import (
    ReferenceEvidenceCompletenessReasonInventory,
)
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.extraction import (
    ReferenceEvidenceExtraction,
)
from projectkoios.ingestion.reference.evidence.identity import (
    ReferenceEvidenceRecordIdentityDerivation,
)
from projectkoios.ingestion.reference.evidence.limitation import (
    ReferenceEvidenceLimitationInventory,
)
from projectkoios.ingestion.reference.evidence.lineage import (
    ReferenceEvidenceLineageVerifier,
)
from projectkoios.ingestion.reference.evidence.source import (
    ReferenceEvidenceSource,
)
from projectkoios.ingestion.reference.evidence.status import (
    ReferenceEvidenceCompleteness,
    ReferenceEvidenceContractStatus,
)
from projectkoios.ingestion.reference.evidence.transcript import (
    ReferenceEvidenceTranscript,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceRecord(AbstractDataObjectActionResult):
    """Aggregate exact producer evidence without granting acceptance."""

    record_id: str
    contract_id: str
    contract_version: str
    contract_status: ReferenceEvidenceContractStatus
    schema_version: int
    media_type: str
    generator_name: str
    generator_version: str
    completeness: ReferenceEvidenceCompleteness
    completeness_reasons: ReferenceEvidenceCompletenessReasonInventory
    source: ReferenceEvidenceSource
    extraction: ReferenceEvidenceExtraction
    transcript: ReferenceEvidenceTranscript
    derivation_audit: ReferenceEvidenceAudit
    limitations: ReferenceEvidenceLimitationInventory

    def __post_init__(self) -> None:
        REFERENCE_EVIDENCE_VALUE_REQUIREMENTS.require_text(
            self.record_id,
            "reference-evidence record_id",
        )
        expected = ReferenceEvidenceRecordIdentityDerivation(
            contract_id=self.contract_id,
            contract_version=self.contract_version,
            contract_status=self.contract_status,
            schema_version=self.schema_version,
            media_type=self.media_type,
            generator_name=self.generator_name,
            generator_version=self.generator_version,
            completeness=self.completeness,
            completeness_reasons=self.completeness_reasons,
            source=self.source,
            extraction=self.extraction,
            transcript=self.transcript,
            derivation_audit=self.derivation_audit,
            limitations=self.limitations,
        ).value
        if self.record_id != expected:
            raise ValueError("reference-evidence record ID is inconsistent")

        # This record explicitly promises the bounded reversible JSON contract.
        # The local import avoids an initialization cycle with the record codec.
        from projectkoios.ingestion.reference.evidence.json.contract import (
            ReferenceEvidenceJsonContract,
        )

        ReferenceEvidenceJsonContract().serialize_bytes(self)

    def require_reusable(self) -> None:
        """Require complete evidence without expanding its authority."""
        if self.completeness is not ReferenceEvidenceCompleteness.COMPLETE:
            reasons = ", ".join(self.completeness_reasons)
            raise ReferenceEvidenceVerificationError(
                f"reference evidence is {self.completeness.value}: {reasons}"
            )
        ReferenceEvidenceLineageVerifier(
            source=self.source,
            extraction=self.extraction,
            transcript=self.transcript,
            audit=self.derivation_audit,
        ).require_complete()
