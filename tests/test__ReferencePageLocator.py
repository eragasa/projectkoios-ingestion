"""Verification for bounded ingestion-owned reference-page location."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest
from projectkoios.ingestion import (
    REFERENCE_LOCATOR_MAX_ANCHORS,
    CleanTranscriptArtifact,
    CleanTranscriptPage,
    CleanTranscriptStatus,
    DerivationAuditStatus,
    IngestionStatus,
    ReferenceEvidenceArtifact,
    ReferenceEvidenceAudit,
    ReferenceEvidenceAuditScope,
    ReferenceEvidenceExtraction,
    ReferenceEvidenceLayerCount,
    ReferenceEvidenceRecord,
    ReferenceEvidenceSource,
    ReferenceEvidenceTranscript,
    ReferenceLocatorLimitError,
    ReferenceLocatorVerificationError,
    ReferencePageLocator,
    ReferencePageLocatorChecker,
    ReferencePageLocatorStatus,
    reference_topic_anchor_identity,
)
from projectkoios.ingestion.identity import stable_id


def evidence(
    *,
    source_digest: str = "a" * 64,
    page_text: str = "The effective-mass model includes Β-decay.",
) -> tuple[ReferenceEvidenceRecord, CleanTranscriptArtifact]:
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
    text = page_text
    text_bytes = text.encode()
    transcript_digest = hashlib.sha256(text_bytes).hexdigest()
    transcript_id = stable_id(
        "clean-transcript-artifact",
        transcription_id,
        document_id,
        "reference:fixture",
        source_blob,
        source_digest,
        (layout_id,),
        (page.page_id,),
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
    transcript = CleanTranscriptArtifact(
        artifact_id=transcript_id,
        transcription_result_id=transcription_id,
        document_id=document_id,
        source_id="reference:fixture",
        source_blob_id=source_blob,
        source_content_hash=source_digest,
        layout_result_ids=(layout_id,),
        pages=(page,),
        blocks=(),
        exclusions=(),
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
    extraction_bytes = b'{"fixture":"extraction"}'
    transcript_bytes = b'{"fixture":"transcript"}'
    audit_bytes = b'{"fixture":"audit"}'
    record = ReferenceEvidenceRecord.create(
        source=ReferenceEvidenceSource(
            blob_id=source_blob,
            hash_algorithm="sha256",
            content_sha256=source_digest,
            byte_length=123,
            media_type="application/pdf",
        ),
        extraction=ReferenceEvidenceExtraction(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                extraction_bytes,
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
        ),
        transcript=ReferenceEvidenceTranscript(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                transcript_bytes,
                media_type=(
                    "application/vnd.projectkoios.ingestion.clean-transcript+json"
                ),
            ),
            artifact_generation=1,
            contract_version="1.0",
            artifact_id=transcript_id,
            status=CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            structured_transcription_result_id=transcription_id,
            layout_result_ids=(layout_id,),
            text_sha256=transcript_digest,
            text_utf8_byte_length=len(text_bytes),
            processor_name="fixture-projector",
            processor_version="1",
            configuration_digest="fixture-configuration",
            warning_count=0,
        ),
        derivation_audit=ReferenceEvidenceAudit(
            artifact=ReferenceEvidenceArtifact.from_bytes(
                audit_bytes,
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
                document_id,
                layout_id,
                manifest_id,
                transcript_id,
                transcription_id,
            ),
            audited_layer_counts=(
                ReferenceEvidenceLayerCount(
                    layer="clean_transcript_artifacts", count=1
                ),
                ReferenceEvidenceLayerCount(layer="extraction_result", count=1),
                ReferenceEvidenceLayerCount(layer="layout_results", count=1),
                ReferenceEvidenceLayerCount(
                    layer="transcription_results", count=1
                ),
            ),
            finding_count=0,
        ),
    )
    return record, transcript


def test__reference_locator__matches_complete_unicode_token_phrases() -> None:
    record, transcript = evidence()
    locator = ReferencePageLocator.create(
        record=record,
        transcript=transcript,
        page_index=0,
        topic_anchor_alternatives=("effective mass", "β decay"),
    )

    result = ReferencePageLocatorChecker().execute(
        record=record,
        transcript=transcript,
        locator=locator,
    )

    assert result.status is ReferencePageLocatorStatus.MATCH
    assert result.matched_topic_anchor_identities == tuple(
        sorted(
            (
                reference_topic_anchor_identity("effective mass"),
                reference_topic_anchor_identity("β decay"),
            )
        )
    )
    assert result.unmatched_topic_anchor_identities == ()
    assert result.page_text_sha256 == transcript.pages[0].text_sha256
    assert "effective mass" not in repr(result)
    assert "β decay" not in repr(result)
    assert not any(
        field in result.__dataclass_fields__
        for field in (
            "locator",
            "text",
            "topic_anchor_alternatives",
            "source_path",
            "quotation",
        )
    )


def test__reference_locator__does_not_match_token_substrings() -> None:
    record, transcript = evidence(page_text="A biomass model is discussed.")
    locator = ReferencePageLocator.create(
        record=record,
        transcript=transcript,
        page_index=0,
        topic_anchor_alternatives=("mass",),
    )

    result = ReferencePageLocatorChecker().execute(
        record=record,
        transcript=transcript,
        locator=locator,
    )

    assert result.status is ReferencePageLocatorStatus.NO_MATCH
    assert result.matched_topic_anchor_identities == ()
    assert result.unmatched_topic_anchor_identities == (
        reference_topic_anchor_identity("mass"),
    )


def test__reference_locator__rejects_normalization_collisions() -> None:
    record, transcript = evidence()

    with pytest.raises(ValueError, match="normalized topic anchors"):
        ReferencePageLocator.create(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=("effective mass", "effective-mass"),
        )


def test__reference_locator__rejects_tampering_and_excess_anchors() -> None:
    record, transcript = evidence()
    locator = ReferencePageLocator.create(
        record=record,
        transcript=transcript,
        page_index=0,
        topic_anchor_alternatives=("effective mass",),
    )

    with pytest.raises(ValueError, match="identity is inconsistent"):
        replace(
            locator,
            locator_id=f"reference-page-locator:sha256:{'0' * 64}",
        )
    with pytest.raises(ReferenceLocatorLimitError, match="count"):
        ReferencePageLocator.create(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=tuple(
                f"anchor {index:02d}"
                for index in range(REFERENCE_LOCATOR_MAX_ANCHORS + 1)
            ),
        )


def test__reference_locator__rejects_cross_source_transcript() -> None:
    record, transcript = evidence()
    other_record, other_transcript = evidence(source_digest="b" * 64)
    locator = ReferencePageLocator.create(
        record=record,
        transcript=transcript,
        page_index=0,
        topic_anchor_alternatives=("effective mass",),
    )

    with pytest.raises(
        ReferenceLocatorVerificationError,
        match="evidence",
    ):
        ReferencePageLocatorChecker().execute(
            record=other_record,
            transcript=other_transcript,
            locator=locator,
        )
