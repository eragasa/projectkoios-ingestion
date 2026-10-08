import pytest
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.json.contract import (
    ReferenceEvidenceJsonContract,
)
from projectkoios.ingestion.reference.evidence.verification.actionizer import (
    ReferenceEvidenceVerificationActionizer,
)
from projectkoios.ingestion.reference.evidence.verification.artifact import (
    ReferenceEvidenceVerifiedArtifact,
)
from projectkoios.ingestion.reference.evidence.verification.request import (
    ReferenceEvidenceVerificationRequest,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

from tests.projectkoios.ingestion.reference.evidence.fixture.record import (
    ReferenceEvidenceRecordFixture,
)


def test__reference_evidence_verification__binds_source_and_artifacts(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    fixture = reference_evidence_record_fixture
    record = ReferenceEvidenceJsonContract().parse_bytes(
        (fixture.fixture_directory / "complete.json").read_bytes()
    )

    result = ReferenceEvidenceVerificationActionizer().action(
        request=ReferenceEvidenceVerificationRequest(
            record=record,
            source_sha256=SHA256Fingerprinter.fingerprint(
                content=fixture.source_bytes
            ),
            source_byte_length=len(fixture.source_bytes),
            source_media_type="application/pdf",
            extraction_artifact=fixture.extraction_bytes,
            clean_transcript_result_bytes=fixture.transcript_bytes,
            derivation_audit_artifact=fixture.audit_bytes,
        )
    )

    assert result.record is record
    assert tuple(result.verified_artifacts) == (
        ReferenceEvidenceVerifiedArtifact.EXTRACTION,
        ReferenceEvidenceVerifiedArtifact.CLEAN_TRANSCRIPT,
        ReferenceEvidenceVerifiedArtifact.DERIVATION_AUDIT,
    )


def test__reference_evidence_verification__rejects_different_source(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    fixture = reference_evidence_record_fixture
    record = fixture.complete_record()

    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="expected source bytes",
    ):
        ReferenceEvidenceVerificationActionizer().action(
            request=ReferenceEvidenceVerificationRequest(
                record=record,
                source_sha256="0" * 64,
                source_byte_length=len(fixture.source_bytes),
                source_media_type="application/pdf",
            )
        )


def test__reference_evidence_verification__rejects_changed_artifact(
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    fixture = reference_evidence_record_fixture

    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="serialized clean-transcript result",
    ):
        ReferenceEvidenceVerificationActionizer().action(
            request=ReferenceEvidenceVerificationRequest(
                record=fixture.complete_record(),
                source_sha256=SHA256Fingerprinter.fingerprint(
                    content=fixture.source_bytes
                ),
                source_byte_length=len(fixture.source_bytes),
                source_media_type="application/pdf",
                clean_transcript_result_bytes=b"changed",
            )
        )
