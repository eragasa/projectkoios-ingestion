"""Bounded deterministic reference-evidence record identity."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.reference.evidence.audit import (
    ReferenceEvidenceAudit,
)
from projectkoios.ingestion.reference.evidence.completeness import (
    ReferenceEvidenceCompletenessReasonInventory,
)
from projectkoios.ingestion.reference.evidence.definition import (
    REFERENCE_EVIDENCE_CONTRACT_ID,
    REFERENCE_EVIDENCE_CONTRACT_VERSION,
    REFERENCE_EVIDENCE_GENERATOR_NAME,
    REFERENCE_EVIDENCE_GENERATOR_VERSION,
    REFERENCE_EVIDENCE_MEDIA_TYPE,
    REFERENCE_EVIDENCE_SCHEMA_VERSION,
)
from projectkoios.ingestion.reference.evidence.extraction import (
    ReferenceEvidenceExtraction,
)
from projectkoios.ingestion.reference.evidence.limitation import (
    ReferenceEvidenceLimitationInventory,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
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
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceRecordIdentityDerivation:
    """Validate and hash the established non-ID record fields."""

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
        if self.contract_id != REFERENCE_EVIDENCE_CONTRACT_ID:
            raise ValueError("unsupported reference-evidence contract ID")
        if self.contract_version != REFERENCE_EVIDENCE_CONTRACT_VERSION:
            raise ValueError("unsupported reference-evidence contract version")
        if self.contract_status is not ReferenceEvidenceContractStatus.PROPOSED:
            raise ValueError("unsupported reference-evidence contract status")
        if (
            isinstance(self.schema_version, bool)
            or self.schema_version != REFERENCE_EVIDENCE_SCHEMA_VERSION
        ):
            raise ValueError("unsupported reference-evidence schema version")
        if self.media_type != REFERENCE_EVIDENCE_MEDIA_TYPE:
            raise ValueError("unsupported reference-evidence media type")
        if self.generator_name != REFERENCE_EVIDENCE_GENERATOR_NAME:
            raise ValueError("unsupported reference-evidence generator")
        if self.generator_version != REFERENCE_EVIDENCE_GENERATOR_VERSION:
            raise ValueError("unsupported reference-evidence generator version")
        if not isinstance(self.completeness, ReferenceEvidenceCompleteness):
            raise TypeError("reference-evidence completeness is unsupported")
        if not isinstance(
            self.completeness_reasons,
            ReferenceEvidenceCompletenessReasonInventory,
        ):
            raise TypeError("completeness_reasons must be a semantic inventory")
        if self.completeness is ReferenceEvidenceCompleteness.COMPLETE:
            if self.completeness_reasons:
                raise ValueError(
                    "complete evidence cannot have failure reasons"
                )
        elif not self.completeness_reasons:
            raise ValueError("non-complete evidence requires explicit reasons")
        if not isinstance(self.source, ReferenceEvidenceSource):
            raise TypeError("reference-evidence source is required")
        if not isinstance(self.extraction, ReferenceEvidenceExtraction):
            raise TypeError("reference-evidence extraction is required")
        if not isinstance(self.transcript, ReferenceEvidenceTranscript):
            raise TypeError("reference-evidence transcript is required")
        if not isinstance(self.derivation_audit, ReferenceEvidenceAudit):
            raise TypeError("reference-evidence derivation audit is required")
        if not isinstance(
            self.limitations, ReferenceEvidenceLimitationInventory
        ):
            raise TypeError("limitations must be a semantic inventory")
        if self.completeness is ReferenceEvidenceCompleteness.COMPLETE:
            ReferenceEvidenceLineageVerifier(
                source=self.source,
                extraction=self.extraction,
                transcript=self.transcript,
                audit=self.derivation_audit,
            ).require_complete()

    @property
    def value(self) -> str:
        """Return the historical record identity after bounded validation."""
        transcript = self.transcript
        audit = self.derivation_audit
        historical_transcript = {
            "artifact": transcript.artifact,
            "result_id": transcript.result_id,
            "status": transcript.status,
            "structured_transcription_result_id": (
                transcript.structured_transcription_result_id
            ),
            "layout_result_ids": tuple(transcript.layout_result_ids),
            "text_sha256": transcript.text_sha256,
            "text_utf8_byte_length": transcript.text_utf8_byte_length,
            "processor_name": transcript.processor_name,
            "processor_version": transcript.processor_version,
            "configuration_digest": transcript.configuration_digest,
            "warning_count": transcript.warning_count,
        }
        historical_audit = {
            "artifact": audit.artifact,
            "contract_version": audit.contract_version,
            "report_id": audit.report_id,
            "status": audit.status,
            "scope": audit.scope,
            "independently_revalidated": audit.independently_revalidated,
            "processor_name": audit.processor_name,
            "processor_version": audit.processor_version,
            "audited_artifact_ids": tuple(audit.audited_artifact_ids),
            "audited_layer_counts": tuple(audit.audited_layer_counts),
            "finding_count": audit.finding_count,
        }
        values = {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "contract_status": self.contract_status,
            "schema_version": self.schema_version,
            "media_type": self.media_type,
            "generator_name": self.generator_name,
            "generator_version": self.generator_version,
            "completeness": self.completeness,
            "completeness_reasons": tuple(self.completeness_reasons),
            "source": self.source,
            "extraction": self.extraction,
            "transcript": historical_transcript,
            "derivation_audit": historical_audit,
            "limitations": tuple(self.limitations),
        }
        identity_input = CanonicalJsonSerializer.serialize_bytes((values,))
        if (
            len(identity_input)
            > REFERENCE_EVIDENCE_LIMITS.maximum_identity_input_bytes
        ):
            raise ReferenceEvidenceLimitError(
                "reference-evidence identity input exceeds size limit"
            )
        digest = SHA256Fingerprinter.fingerprint(content=identity_input)
        return f"reference-evidence-record:sha256:{digest}"
