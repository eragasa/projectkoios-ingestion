"""Immutable fixture owner for exact reference page-location evidence."""

from dataclasses import dataclass

from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    CleanTranscriptPage,
    CleanTranscriptStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import IngestionStatus
from projectkoios.ingestion.provenance.audit import DerivationAuditStatus
from projectkoios.ingestion.reference.evidence.artifact import (
    ReferenceEvidenceArtifact,
)
from projectkoios.ingestion.reference.evidence.audit import (
    ReferenceEvidenceAudit,
    ReferenceEvidenceAuditScope,
)
from projectkoios.ingestion.reference.evidence.completeness import (
    REFERENCE_EVIDENCE_COMPLETE_REASONS,
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
    ReferenceEvidenceTranscript,
)
from projectkoios.ingestion.reference.page.location.anchor import (
    ReferenceTopicAnchor,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorInventory,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class ReferencePageLocationFixture:
    """Build deterministic reference page-location inputs."""

    source_digest: str = "a" * 64
    page_text: str = "The effective-mass model includes Β-decay."

    def anchors(self, *texts: str) -> ReferenceTopicAnchorInventory:
        """Return one explicit semantic anchor inventory."""
        return ReferenceTopicAnchorInventory(
            *(ReferenceTopicAnchor(text) for text in texts)
        )

    def evidence(
        self,
        *,
        source_digest: str | None = None,
        page_text: str | None = None,
    ) -> tuple[ReferenceEvidenceRecord, CleanTranscript]:
        source_digest = (
            self.source_digest if source_digest is None else source_digest
        )
        page_text = self.page_text if page_text is None else page_text
        source_blob = f"blob:sha256:{source_digest}"
        document_id = stable_id("document", source_digest)
        layout_id = stable_id("layout", source_digest)
        transcription_id = stable_id("transcription", source_digest)
        page = CleanTranscriptPage.create(
            page_index=0,
            printed_page_label="1",
            block_record_ids=(),
            text=page_text,
        )
        text = f"{page_text}\n"
        text_bytes = text.encode()
        transcript_digest = SHA256Fingerprinter.fingerprint(content=text_bytes)
        transcript_id = stable_id(
            "clean-transcript-result",
            transcription_id,
            document_id,
            "reference:fixture",
            source_blob,
            source_digest,
            (layout_id,),
            (page.page_id,),
            (),
            (),
            (),
            (),
            (),
            (),
            transcript_digest,
            len(text_bytes),
            CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            (),
            "fixture-projector",
            "1",
            "fixture-configuration",
        )
        transcript = CleanTranscript(
            result_id=transcript_id,
            transcription_result_id=transcription_id,
            document_id=document_id,
            source_id="reference:fixture",
            source_blob_id=source_blob,
            source_content_hash=source_digest,
            layout_result_ids=(layout_id,),
            pages=(page,),
            blocks=(),
            exclusions=(),
            dehyphenation_decisions=(),
            page_number_classifications=(),
            publisher_front_matter=(),
            private_use_glyph_findings=(),
            text=text,
            text_sha256=transcript_digest,
            utf8_byte_length=len(text_bytes),
            status=CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            warnings=(),
            processor_name="fixture-projector",
            processor_version="1",
            configuration_digest="fixture-configuration",
        )
        manifest_id = stable_id("manifest", source_digest)
        audit_id = stable_id("audit", source_digest)
        evidence_source = ReferenceEvidenceSource(
            blob_id=source_blob,
            hash_algorithm="sha256",
            content_sha256=source_digest,
            byte_length=123,
            media_type="application/pdf",
        )
        extraction = ReferenceEvidenceExtraction(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                b'{"fixture":"extraction"}',
                media_type=(
                    "application/vnd.projectkoios.ingestion.extraction+json"
                ),
            ),
            contract_version="2.2",
            manifest_id=manifest_id,
            document_id=document_id,
            status=IngestionStatus.COMPLETED,
            extractor_name="fixture-extractor",
            extractor_version="1",
            configuration_digest="fixture-configuration",
            warning_count=0,
        )
        evidence_transcript = ReferenceEvidenceTranscript(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                b'{"fixture":"transcript"}',
                media_type=(
                    "application/vnd.projectkoios.ingestion.clean-transcript+json"
                ),
            ),
            result_id=transcript_id,
            status=CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            structured_transcription_result_id=transcription_id,
            layout_result_ids=ReferenceEvidenceLayoutIdentityInventory(
                layout_id
            ),
            text_sha256=transcript_digest,
            text_utf8_byte_length=len(text_bytes),
            processor_name="fixture-projector",
            processor_version="1",
            configuration_digest="fixture-configuration",
            warning_count=0,
        )
        audit = ReferenceEvidenceAudit(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                b'{"fixture":"audit"}',
                media_type=(
                    "application/vnd.projectkoios.ingestion.derivation-audit+json"
                ),
            ),
            contract_version="1.0",
            report_id=audit_id,
            status=DerivationAuditStatus.PASSED,
            scope=(
                ReferenceEvidenceAuditScope.RECORDED_PRODUCER_DERIVATION_AUDIT
            ),
            independently_revalidated=False,
            processor_name="fixture-auditor",
            processor_version="1",
            audited_artifact_ids=(
                ReferenceEvidenceAuditArtifactIdentityInventory(
                    document_id,
                    layout_id,
                    manifest_id,
                    transcript_id,
                    transcription_id,
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
        # Direct construction preserves the legacy synthetic digest used by
        # page-location identity compatibility tests. Projection behavior has
        # a separate producer-graph fixture and actionizer test boundary.
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
            source=evidence_source,
            extraction=extraction,
            transcript=evidence_transcript,
            derivation_audit=audit,
            limitations=REFERENCE_EVIDENCE_LIMITATIONS,
        )
        record = ReferenceEvidenceRecord(
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
        return record, transcript
