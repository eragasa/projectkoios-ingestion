"""Immutable-record fixtures for reference-evidence boundary tests."""

from dataclasses import dataclass, replace
from pathlib import Path

from projectkoios.ingestion.clean_transcript import (
    CleanTranscriptStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    IngestionStatus,
)
from projectkoios.ingestion.provenance.audit import (
    DerivationAuditStatus,
)
from projectkoios.ingestion.reference.evidence.artifact import (
    ReferenceEvidenceArtifact,
)
from projectkoios.ingestion.reference.evidence.audit import (
    REFERENCE_EVIDENCE_DERIVATION_AUDIT_MEDIA_TYPE,
    ReferenceEvidenceAudit,
    ReferenceEvidenceAuditScope,
)
from projectkoios.ingestion.reference.evidence.completeness import (
    REFERENCE_EVIDENCE_COMPLETE_REASONS,
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
    REFERENCE_EVIDENCE_EXTRACTION_MEDIA_TYPE,
    ReferenceEvidenceExtraction,
)
from projectkoios.ingestion.reference.evidence.identity import (
    ReferenceEvidenceRecordIdentityDerivation,
)
from projectkoios.ingestion.reference.evidence.layer import (
    ReferenceEvidenceLayerCount,
    ReferenceEvidenceLayerCountInventory,
)
from projectkoios.ingestion.reference.evidence.layout import (
    ReferenceEvidenceLayoutIdentityInventory,
)
from projectkoios.ingestion.reference.evidence.limitation import (
    REFERENCE_EVIDENCE_LIMITATIONS,
)
from projectkoios.ingestion.reference.evidence.lineage import (
    ReferenceEvidenceAuditArtifactIdentityInventory,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.evidence.source import (
    ReferenceEvidenceSource,
)
from projectkoios.ingestion.reference.evidence.status import (
    ReferenceEvidenceCompleteness,
    ReferenceEvidenceContractStatus,
)
from projectkoios.ingestion.reference.evidence.transcript import (
    REFERENCE_EVIDENCE_CLEAN_TRANSCRIPT_MEDIA_TYPE,
    ReferenceEvidenceTranscript,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceRecordFixture:
    """Build deterministic immutable-record and verification scenarios."""

    fixture_directory: Path
    source_bytes: bytes = b"sanitized reference-evidence fixture source\n"
    extraction_bytes: bytes = b'{"sanitized":"extraction"}\n'
    transcript_bytes: bytes = b'{"sanitized":"automated transcript identity"}\n'
    audit_bytes: bytes = b'{"sanitized":"recorded audit identity"}\n'

    def record_with_transcript(
        self,
        *,
        original: ReferenceEvidenceRecord,
        transcript: ReferenceEvidenceTranscript,
    ) -> ReferenceEvidenceRecord:
        """Return one complete scenario with changed transcript evidence."""
        derivation = ReferenceEvidenceRecordIdentityDerivation(
            contract_id=original.contract_id,
            contract_version=original.contract_version,
            contract_status=original.contract_status,
            schema_version=original.schema_version,
            media_type=original.media_type,
            generator_name=original.generator_name,
            generator_version=original.generator_version,
            completeness=original.completeness,
            completeness_reasons=original.completeness_reasons,
            source=original.source,
            extraction=original.extraction,
            transcript=transcript,
            derivation_audit=original.derivation_audit,
            limitations=original.limitations,
        )
        return replace(
            original,
            record_id=derivation.value,
            transcript=transcript,
        )

    def incomplete_record(
        self,
        *,
        original: ReferenceEvidenceRecord,
        reason: str,
    ) -> ReferenceEvidenceRecord:
        """Return one explicit incomplete-evidence scenario."""
        completeness = ReferenceEvidenceCompleteness.INCOMPLETE
        reasons = ReferenceEvidenceCompletenessReasonInventory(reason)
        derivation = ReferenceEvidenceRecordIdentityDerivation(
            contract_id=original.contract_id,
            contract_version=original.contract_version,
            contract_status=original.contract_status,
            schema_version=original.schema_version,
            media_type=original.media_type,
            generator_name=original.generator_name,
            generator_version=original.generator_version,
            completeness=completeness,
            completeness_reasons=reasons,
            source=original.source,
            extraction=original.extraction,
            transcript=original.transcript,
            derivation_audit=original.derivation_audit,
            limitations=original.limitations,
        )
        return replace(
            original,
            record_id=derivation.value,
            completeness=completeness,
            completeness_reasons=reasons,
        )

    def complete_record(self) -> ReferenceEvidenceRecord:
        """Return the canonical complete immutable-record scenario."""
        source_sha256 = SHA256Fingerprinter.fingerprint(
            content=self.source_bytes
        )
        manifest_id = stable_id("manifest", "sanitized-fixture")
        document_id = stable_id("document", "sanitized-fixture")
        layout_id = stable_id("layout", "sanitized-fixture")
        transcription_id = stable_id("transcription", "sanitized-fixture")
        clean_id = stable_id("clean-transcript-result", "sanitized-fixture")
        source = ReferenceEvidenceSource(
            blob_id=f"blob:sha256:{source_sha256}",
            hash_algorithm="sha256",
            content_sha256=source_sha256,
            byte_length=len(self.source_bytes),
            media_type="application/pdf",
        )
        extraction = ReferenceEvidenceExtraction(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                self.extraction_bytes,
                media_type=REFERENCE_EVIDENCE_EXTRACTION_MEDIA_TYPE,
            ),
            contract_version="2.2",
            manifest_id=manifest_id,
            document_id=document_id,
            status=IngestionStatus.COMPLETED,
            extractor_name="sanitized-fixture-extractor",
            extractor_version="1",
            configuration_digest=stable_id(
                "configuration",
                "sanitized-fixture",
            ),
            warning_count=0,
        )
        transcript = ReferenceEvidenceTranscript(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                self.transcript_bytes,
                media_type=REFERENCE_EVIDENCE_CLEAN_TRANSCRIPT_MEDIA_TYPE,
            ),
            result_id=clean_id,
            status=CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            structured_transcription_result_id=transcription_id,
            layout_result_ids=ReferenceEvidenceLayoutIdentityInventory(
                layout_id
            ),
            text_sha256=SHA256Fingerprinter.fingerprint(
                content=b"sanitized transcript text\n"
            ),
            text_utf8_byte_length=len(b"sanitized transcript text\n"),
            processor_name="sanitized-fixture-projector",
            processor_version="1",
            configuration_digest=stable_id(
                "configuration",
                "sanitized-transcript",
            ),
            warning_count=1,
        )
        audit = ReferenceEvidenceAudit(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                self.audit_bytes,
                media_type=REFERENCE_EVIDENCE_DERIVATION_AUDIT_MEDIA_TYPE,
            ),
            contract_version="1.0",
            report_id=stable_id(
                "derivation-audit-report",
                "sanitized-fixture",
            ),
            status=DerivationAuditStatus.PASSED,
            scope=(
                ReferenceEvidenceAuditScope.RECORDED_PRODUCER_DERIVATION_AUDIT
            ),
            independently_revalidated=False,
            processor_name="sanitized-fixture-auditor",
            processor_version="1",
            audited_artifact_ids=(
                ReferenceEvidenceAuditArtifactIdentityInventory(
                    manifest_id,
                    document_id,
                    layout_id,
                    transcription_id,
                    clean_id,
                )
            ),
            audited_layer_counts=ReferenceEvidenceLayerCountInventory(
                ReferenceEvidenceLayerCount(
                    layer="clean_transcripts",
                    count=1,
                ),
                ReferenceEvidenceLayerCount(
                    layer="extraction_result",
                    count=1,
                ),
                ReferenceEvidenceLayerCount(
                    layer="layout_results",
                    count=1,
                ),
                ReferenceEvidenceLayerCount(
                    layer="transcription_results",
                    count=1,
                ),
            ),
            finding_count=0,
        )
        derivation = ReferenceEvidenceRecordIdentityDerivation(
            contract_id=REFERENCE_EVIDENCE_CONTRACT_ID,
            contract_version=REFERENCE_EVIDENCE_CONTRACT_VERSION,
            contract_status=ReferenceEvidenceContractStatus.PROPOSED,
            schema_version=REFERENCE_EVIDENCE_SCHEMA_VERSION,
            media_type=REFERENCE_EVIDENCE_MEDIA_TYPE,
            generator_name=REFERENCE_EVIDENCE_GENERATOR_NAME,
            generator_version=REFERENCE_EVIDENCE_GENERATOR_VERSION,
            completeness=ReferenceEvidenceCompleteness.COMPLETE,
            completeness_reasons=REFERENCE_EVIDENCE_COMPLETE_REASONS,
            source=source,
            extraction=extraction,
            transcript=transcript,
            derivation_audit=audit,
            limitations=REFERENCE_EVIDENCE_LIMITATIONS,
        )
        return ReferenceEvidenceRecord(
            record_id=derivation.value,
            contract_id=derivation.contract_id,
            contract_version=derivation.contract_version,
            contract_status=derivation.contract_status,
            schema_version=derivation.schema_version,
            media_type=derivation.media_type,
            generator_name=derivation.generator_name,
            generator_version=derivation.generator_version,
            completeness=derivation.completeness,
            completeness_reasons=derivation.completeness_reasons,
            source=derivation.source,
            extraction=derivation.extraction,
            transcript=derivation.transcript,
            derivation_audit=derivation.derivation_audit,
            limitations=derivation.limitations,
        )
