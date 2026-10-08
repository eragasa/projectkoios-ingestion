"""Deterministic complete reference-evidence projection action."""

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.reference.evidence.artifact import (
    ReferenceEvidenceArtifact,
)
from projectkoios.ingestion.reference.evidence.audit import (
    REFERENCE_EVIDENCE_DERIVATION_AUDIT_MEDIA_TYPE,
    ReferenceEvidenceAudit,
    ReferenceEvidenceAuditScope,
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
    REFERENCE_EVIDENCE_EXTRACTION_MEDIA_TYPE,
    ReferenceEvidenceExtraction,
)
from projectkoios.ingestion.reference.evidence.identity import (
    ReferenceEvidenceRecordIdentityDerivation,
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
from projectkoios.ingestion.reference.evidence.projection.artifact import (
    ReferenceEvidenceProjectionArtifactVerifier,
)
from projectkoios.ingestion.reference.evidence.projection.lineage import (
    ReferenceEvidenceProjectionLineageVerifier,
)
from projectkoios.ingestion.reference.evidence.projection.request import (
    ReferenceEvidenceProjectionRequest,
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


class ReferenceEvidenceProjectionActionizer(
    DataObjectActionizer[
        ReferenceEvidenceProjectionRequest,
        ReferenceEvidenceRecord,
    ]
):
    """Build complete evidence from exact already-produced artifacts."""

    __slots__ = ()

    def action(
        self,
        *,
        request: ReferenceEvidenceProjectionRequest,
    ) -> ReferenceEvidenceRecord:
        """Validate exact lineage and return one immutable evidence record."""
        if type(request) is not ReferenceEvidenceProjectionRequest:
            raise TypeError(
                "request must be ReferenceEvidenceProjectionRequest"
            )
        ReferenceEvidenceProjectionArtifactVerifier(request).verify()
        layer_counts = ReferenceEvidenceProjectionLineageVerifier(
            request
        ).verified_layer_counts()
        extraction_result = request.extraction_result
        clean_transcript = request.clean_transcript
        derivation_audit = request.derivation_audit
        document = extraction_result.document
        source = document.source
        manifest = extraction_result.manifest
        evidence_source = ReferenceEvidenceSource(
            blob_id=source.blob_id,
            hash_algorithm=source.hash_algorithm,
            content_sha256=source.content_hash,
            byte_length=source.byte_length,
            media_type=source.media_type,
        )
        extraction = ReferenceEvidenceExtraction(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                request.extraction_artifact,
                media_type=REFERENCE_EVIDENCE_EXTRACTION_MEDIA_TYPE,
            ),
            contract_version=document.contract_version,
            manifest_id=manifest.manifest_id,
            document_id=document.document_id,
            status=manifest.status,
            extractor_name=manifest.extractor_name,
            extractor_version=manifest.extractor_version,
            configuration_digest=manifest.configuration_digest,
            warning_count=len(extraction_result.warnings),
        )
        transcript = ReferenceEvidenceTranscript(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                request.clean_transcript_result_bytes,
                media_type=REFERENCE_EVIDENCE_CLEAN_TRANSCRIPT_MEDIA_TYPE,
            ),
            result_id=clean_transcript.result_id,
            status=clean_transcript.status,
            structured_transcription_result_id=(
                clean_transcript.transcription_result_id
            ),
            layout_result_ids=ReferenceEvidenceLayoutIdentityInventory(
                *clean_transcript.layout_result_ids
            ),
            text_sha256=clean_transcript.text_sha256,
            text_utf8_byte_length=clean_transcript.utf8_byte_length,
            processor_name=clean_transcript.processor_name,
            processor_version=clean_transcript.processor_version,
            configuration_digest=clean_transcript.configuration_digest,
            warning_count=len(clean_transcript.warnings),
        )
        audit = ReferenceEvidenceAudit(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                request.derivation_audit_artifact,
                media_type=REFERENCE_EVIDENCE_DERIVATION_AUDIT_MEDIA_TYPE,
            ),
            contract_version=derivation_audit.contract_version,
            report_id=derivation_audit.report_id,
            status=derivation_audit.status,
            scope=ReferenceEvidenceAuditScope.RECORDED_PRODUCER_DERIVATION_AUDIT,
            independently_revalidated=False,
            processor_name=derivation_audit.processor_name,
            processor_version=derivation_audit.processor_version,
            audited_artifact_ids=(
                ReferenceEvidenceAuditArtifactIdentityInventory(
                    *derivation_audit.audited_artifact_ids
                )
            ),
            audited_layer_counts=layer_counts,
            finding_count=len(derivation_audit.findings),
        )
        reasons = ReferenceEvidenceCompletenessReasonInventory()
        derivation = ReferenceEvidenceRecordIdentityDerivation(
            contract_id=REFERENCE_EVIDENCE_CONTRACT_ID,
            contract_version=REFERENCE_EVIDENCE_CONTRACT_VERSION,
            contract_status=ReferenceEvidenceContractStatus.PROPOSED,
            schema_version=REFERENCE_EVIDENCE_SCHEMA_VERSION,
            media_type=REFERENCE_EVIDENCE_MEDIA_TYPE,
            generator_name=REFERENCE_EVIDENCE_GENERATOR_NAME,
            generator_version=REFERENCE_EVIDENCE_GENERATOR_VERSION,
            completeness=ReferenceEvidenceCompleteness.COMPLETE,
            completeness_reasons=reasons,
            source=evidence_source,
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
