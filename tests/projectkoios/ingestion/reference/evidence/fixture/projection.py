"""Producer-graph fixtures for reference-evidence projection tests."""

from dataclasses import dataclass

from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    CleanTranscriptPage,
    CleanTranscriptStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.models import (
    ExtractedDocument,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    SourceDocument,
)
from projectkoios.ingestion.provenance.audit import (
    DerivationAuditReport,
)
from projectkoios.ingestion.reference.evidence.projection.request import (
    ReferenceEvidenceProjectionRequest,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceProjectionFixture:
    """Build one deterministic producer graph for projection tests."""

    source_bytes: bytes = b"sanitized reference-evidence fixture source\n"

    def complete_request(
        self,
        *,
        source_bytes: bytes | None = None,
        page_text: str = "sanitized transcript text",
    ) -> ReferenceEvidenceProjectionRequest:
        """Build one complete producer graph and its exact JSON artifacts."""
        source = SourceDocument.from_bytes(
            self.source_bytes if source_bytes is None else source_bytes,
            source_id="reference:projection-fixture",
            media_type="application/pdf",
            locator="private/sanitized-fixture.pdf",
        )
        document = ExtractedDocument.create(source=source, pages=())
        manifest = IngestionManifest.create(
            source=source,
            extractor_name="sanitized-fixture-extractor",
            extractor_version="1",
            configuration_digest=stable_id(
                "configuration",
                "sanitized-extraction",
            ),
            object_ids=(document.document_id,),
            warning_ids=(),
            status=IngestionStatus.COMPLETED,
            started_at="2025-01-01T00:00:00+00:00",
            completed_at="2025-01-01T00:00:01+00:00",
        )
        extraction = ExtractionResult(document=document, manifest=manifest)
        extraction_artifact = (
            CanonicalJsonSerializer.serialize_text(extraction) + "\n"
        ).encode("utf-8")

        layout_id = stable_id("layout", source.content_hash)
        transcription_id = stable_id("transcription", source.content_hash)
        page = CleanTranscriptPage.create(
            page_index=0,
            printed_page_label="1",
            block_record_ids=(),
            text=page_text,
        )
        text = f"{page_text}\n"
        text_bytes = text.encode("utf-8")
        text_sha256 = SHA256Fingerprinter.fingerprint(content=text_bytes)
        processor_name = "sanitized-fixture-projector"
        processor_version = "1"
        configuration_digest = stable_id(
            "configuration",
            "sanitized-transcript",
        )
        transcript_id = stable_id(
            "clean-transcript-result",
            transcription_id,
            document.document_id,
            source.source_id,
            source.blob_id,
            source.content_hash,
            (layout_id,),
            (page.page_id,),
            (),
            (),
            (),
            (),
            (),
            (),
            text_sha256,
            len(text_bytes),
            CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            (),
            processor_name,
            processor_version,
            configuration_digest,
        )
        transcript = CleanTranscript(
            result_id=transcript_id,
            transcription_result_id=transcription_id,
            document_id=document.document_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            layout_result_ids=(layout_id,),
            pages=(page,),
            blocks=(),
            exclusions=(),
            dehyphenation_decisions=(),
            page_number_classifications=(),
            publisher_front_matter=(),
            private_use_glyph_findings=(),
            text=text,
            text_sha256=text_sha256,
            utf8_byte_length=len(text_bytes),
            status=CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            warnings=(),
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )
        transcript_artifact = (
            CanonicalJsonSerializer.serialize_text(transcript) + "\n"
        ).encode("utf-8")

        audit = DerivationAuditReport.create(
            source=source,
            document_id=document.document_id,
            audited_artifact_ids=(
                manifest.manifest_id,
                document.document_id,
                transcription_id,
                transcript.result_id,
                layout_id,
            ),
            audited_layer_counts=(
                ("clean_transcripts", "1"),
                ("extraction_result", "1"),
                ("layout_results", "1"),
                ("transcription_results", "1"),
            ),
            findings=(),
            processor_name="sanitized-fixture-auditor",
            processor_version="1",
        )
        audit_artifact = (
            CanonicalJsonSerializer.serialize_text(audit) + "\n"
        ).encode("utf-8")
        return ReferenceEvidenceProjectionRequest(
            extraction_result=extraction,
            extraction_artifact=extraction_artifact,
            clean_transcript=transcript,
            clean_transcript_result_bytes=transcript_artifact,
            derivation_audit=audit,
            derivation_audit_artifact=audit_artifact,
        )
