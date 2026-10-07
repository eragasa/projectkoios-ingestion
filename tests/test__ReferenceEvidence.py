from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    DerivationAuditStatus,
    IngestionStatus,
)
from projectkoios.ingestion.clean_transcript import CleanTranscriptStatus
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.reference_evidence import (
    REFERENCE_EVIDENCE_CONTRACT_VERSION,
    REFERENCE_EVIDENCE_MAX_BYTES,
    ReferenceEvidenceArtifact,
    ReferenceEvidenceAudit,
    ReferenceEvidenceAuditScope,
    ReferenceEvidenceCompleteness,
    ReferenceEvidenceExtraction,
    ReferenceEvidenceLayerCount,
    ReferenceEvidenceLimitError,
    ReferenceEvidenceParseError,
    ReferenceEvidenceRecord,
    ReferenceEvidenceSource,
    ReferenceEvidenceTranscript,
    ReferenceEvidenceVerificationError,
    parse_reference_evidence,
    serialize_reference_evidence,
    verify_reference_evidence,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

FIXTURES = Path(__file__).parent / "fixtures" / "reference_evidence"
_SOURCE_BYTES = b"sanitized reference-evidence fixture source\n"
_EXTRACTION_BYTES = b'{"sanitized":"extraction"}\n'
_TRANSCRIPT_BYTES = b'{"sanitized":"automated transcript identity"}\n'
_AUDIT_BYTES = b'{"sanitized":"recorded audit identity"}\n'


def _artifact(content: bytes, media_type: str) -> ReferenceEvidenceArtifact:
    return ReferenceEvidenceArtifact.from_bytes(
        content,
        media_type=media_type,
    )


def _record() -> ReferenceEvidenceRecord:
    source_sha256 = SHA256Fingerprinter.fingerprint(content=_SOURCE_BYTES)
    manifest_id = stable_id("manifest", "sanitized-fixture")
    document_id = stable_id("document", "sanitized-fixture")
    layout_id = stable_id("layout", "sanitized-fixture")
    transcription_id = stable_id("transcription", "sanitized-fixture")
    clean_id = stable_id("clean-transcript-result", "sanitized-fixture")
    return ReferenceEvidenceRecord.create(
        source=ReferenceEvidenceSource(
            blob_id=f"blob:sha256:{source_sha256}",
            hash_algorithm="sha256",
            content_sha256=source_sha256,
            byte_length=len(_SOURCE_BYTES),
            media_type="application/pdf",
        ),
        extraction=ReferenceEvidenceExtraction(
            artifact=_artifact(
                _EXTRACTION_BYTES,
                "application/vnd.projectkoios.ingestion.extraction+json",
            ),
            contract_version="2.2",
            manifest_id=manifest_id,
            document_id=document_id,
            status=IngestionStatus.COMPLETED,
            extractor_name="sanitized-fixture-extractor",
            extractor_version="1",
            configuration_digest=stable_id(
                "configuration", "sanitized-fixture"
            ),
            warning_count=0,
        ),
        transcript=ReferenceEvidenceTranscript(
            artifact=_artifact(
                _TRANSCRIPT_BYTES,
                "application/vnd.projectkoios.ingestion.clean-transcript+json",
            ),
            result_id=clean_id,
            status=CleanTranscriptStatus.AUTOMATED_UNREVIEWED,
            structured_transcription_result_id=transcription_id,
            layout_result_ids=(layout_id,),
            text_sha256=SHA256Fingerprinter.fingerprint(
                content=b"sanitized transcript text\n"
            ),
            text_utf8_byte_length=len(b"sanitized transcript text\n"),
            processor_name="sanitized-fixture-projector",
            processor_version="1",
            configuration_digest=stable_id(
                "configuration", "sanitized-transcript"
            ),
            warning_count=1,
        ),
        derivation_audit=ReferenceEvidenceAudit(
            artifact=_artifact(
                _AUDIT_BYTES,
                "application/vnd.projectkoios.ingestion.derivation-audit+json",
            ),
            contract_version="1.0",
            report_id=stable_id("derivation-audit-report", "sanitized-fixture"),
            status=DerivationAuditStatus.PASSED,
            scope=(
                ReferenceEvidenceAuditScope.RECORDED_PRODUCER_DERIVATION_AUDIT
            ),
            independently_revalidated=False,
            processor_name="sanitized-fixture-auditor",
            processor_version="1",
            audited_artifact_ids=(
                manifest_id,
                document_id,
                layout_id,
                transcription_id,
                clean_id,
            ),
            audited_layer_counts=(
                ReferenceEvidenceLayerCount(layer="clean_transcripts", count=1),
                ReferenceEvidenceLayerCount(layer="extraction_result", count=1),
                ReferenceEvidenceLayerCount(layer="layout_results", count=1),
                ReferenceEvidenceLayerCount(
                    layer="transcription_results", count=1
                ),
            ),
            finding_count=0,
        ),
    )


def test__reference_evidence__fixture_is_canonical_and_content_addressed() -> (
    None
):
    expected = (FIXTURES / "complete.json").read_bytes()
    first = serialize_reference_evidence(_record())
    second = serialize_reference_evidence(_record())

    assert first == second == expected
    parsed = parse_reference_evidence(expected)
    assert parsed == _record()
    assert parsed.contract_version == REFERENCE_EVIDENCE_CONTRACT_VERSION
    assert parsed.completeness is ReferenceEvidenceCompleteness.COMPLETE
    assert (
        parsed.transcript.status is CleanTranscriptStatus.AUTOMATED_UNREVIEWED
    )
    assert parsed.derivation_audit.independently_revalidated is False
    assert b"path" not in expected.lower()
    assert b"filename" not in expected.lower()
    assert b"workspace" not in expected.lower()


def test__reference_evidence__verification_binds_source_and_artifacts() -> None:
    record = parse_reference_evidence((FIXTURES / "complete.json").read_bytes())

    verify_reference_evidence(
        record,
        source_sha256=SHA256Fingerprinter.fingerprint(content=_SOURCE_BYTES),
        source_byte_length=len(_SOURCE_BYTES),
        source_media_type="application/pdf",
        extraction_artifact=_EXTRACTION_BYTES,
        clean_transcript_result_bytes=_TRANSCRIPT_BYTES,
        derivation_audit_artifact=_AUDIT_BYTES,
    )

    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="expected source bytes",
    ):
        verify_reference_evidence(
            record,
            source_sha256="0" * 64,
            source_byte_length=len(_SOURCE_BYTES),
            source_media_type="application/pdf",
        )
    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="serialized clean-transcript result",
    ):
        verify_reference_evidence(
            record,
            source_sha256=SHA256Fingerprinter.fingerprint(
                content=_SOURCE_BYTES
            ),
            source_byte_length=len(_SOURCE_BYTES),
            source_media_type="application/pdf",
            clean_transcript_result_bytes=b"changed",
        )


def test__reference_evidence__changed_bound_evidence_changes_identity() -> None:
    original = _record()
    changed_transcript = replace(
        original.transcript,
        text_sha256=SHA256Fingerprinter.fingerprint(
            content=b"changed transcript"
        ),
    )
    changed = ReferenceEvidenceRecord.create(
        source=original.source,
        extraction=original.extraction,
        transcript=changed_transcript,
        derivation_audit=original.derivation_audit,
    )

    assert changed.record_id != original.record_id
    assert serialize_reference_evidence(
        changed
    ) != serialize_reference_evidence(original)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("unknown_root_field", "unknown fields"),
        ("removed_generation_key", "unknown fields"),
        ("removed_contract_key", "unknown fields"),
        (
            "unsupported_version",
            "unsupported reference-evidence contract version",
        ),
        ("noncanonical", "not canonical"),
        ("duplicate_field", "duplicate JSON object field"),
        ("contradictory_audit", "requires a recorded passing audit"),
    ),
)
def test__reference_evidence__strict_parse_rejects_external_mutation(
    mutation: str,
    message: str,
) -> None:
    payload = (FIXTURES / "complete.json").read_bytes()
    value = json.loads(payload)
    if mutation == "unknown_root_field":
        value["external"] = True
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "removed_generation_key":
        value["transcript"]["artifact_generation"] = 1
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "removed_contract_key":
        value["transcript"]["contract_version"] = "1.0"
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "unsupported_version":
        value["contract_version"] = "0.2.0"
        payload = CanonicalJsonSerializer.serialize_text(value).encode()
    elif mutation == "noncanonical":
        payload += b"\n"
    elif mutation == "duplicate_field":
        payload = payload[:-1] + b',"schema_version":1}'
    else:
        value["derivation_audit"]["status"] = "failed"
        payload = CanonicalJsonSerializer.serialize_text(value).encode()

    with pytest.raises(ReferenceEvidenceParseError, match=message):
        parse_reference_evidence(payload)


def test__reference_evidence__incomplete_record_fails_reuse() -> None:
    complete = _record()
    incomplete = ReferenceEvidenceRecord.create(
        source=complete.source,
        extraction=complete.extraction,
        transcript=complete.transcript,
        derivation_audit=complete.derivation_audit,
        completeness=ReferenceEvidenceCompleteness.INCOMPLETE,
        completeness_reasons=("consumer_fixture_deliberately_incomplete",),
    )

    with pytest.raises(ReferenceEvidenceVerificationError, match="incomplete"):
        incomplete.require_reusable()
    with pytest.raises(ReferenceEvidenceVerificationError, match="incomplete"):
        parse_reference_evidence(serialize_reference_evidence(incomplete))


def test__reference_evidence__malformed_input_fails_explicitly() -> None:
    with pytest.raises(ReferenceEvidenceParseError, match="malformed JSON"):
        parse_reference_evidence(b'{"contract_id":')


def test__reference_evidence__oversized_input_fails_before_parse() -> None:
    with pytest.raises(ReferenceEvidenceLimitError, match="size limit"):
        parse_reference_evidence(b" " * (REFERENCE_EVIDENCE_MAX_BYTES + 1))
