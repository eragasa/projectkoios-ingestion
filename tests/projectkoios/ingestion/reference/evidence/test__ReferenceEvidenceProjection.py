from dataclasses import replace

import pytest
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.projection.actionizer import (
    ReferenceEvidenceProjectionActionizer,
)
from projectkoios.ingestion.reference.evidence.status import (
    ReferenceEvidenceCompleteness,
)

from tests.projectkoios.ingestion.reference.evidence.fixture.projection import (
    ReferenceEvidenceProjectionFixture,
)


def test__reference_evidence_projection__projects_complete_lineage(
    reference_evidence_projection_fixture: ReferenceEvidenceProjectionFixture,
) -> None:
    request = reference_evidence_projection_fixture.complete_request()

    result = ReferenceEvidenceProjectionActionizer().action(request=request)

    assert result.completeness is ReferenceEvidenceCompleteness.COMPLETE
    assert result.source.content_sha256 == (
        request.extraction_result.document.source.content_hash
    )
    assert result.extraction.artifact.byte_length == len(
        request.extraction_artifact
    )
    assert result.transcript.artifact.byte_length == len(
        request.clean_transcript_result_bytes
    )
    assert result.derivation_audit.artifact.byte_length == len(
        request.derivation_audit_artifact
    )
    result.require_reusable()


def test__reference_evidence_projection__requires_typed_request() -> None:
    with pytest.raises(
        TypeError,
        match="request must be ReferenceEvidenceProjectionRequest",
    ):
        ReferenceEvidenceProjectionActionizer().action(request=object())  # type: ignore[arg-type]


def test__reference_evidence_projection__rejects_extraction_mismatch(
    reference_evidence_projection_fixture: ReferenceEvidenceProjectionFixture,
) -> None:
    request = reference_evidence_projection_fixture.complete_request()

    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="fields do not match ExtractionResult",
    ):
        ReferenceEvidenceProjectionActionizer().action(
            request=replace(request, extraction_artifact=b"{}\n")
        )


def test__reference_evidence_projection__rejects_transcript_mismatch(
    reference_evidence_projection_fixture: ReferenceEvidenceProjectionFixture,
) -> None:
    request = reference_evidence_projection_fixture.complete_request()

    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="serialized clean-transcript result does not match",
    ):
        ReferenceEvidenceProjectionActionizer().action(
            request=replace(
                request,
                clean_transcript_result_bytes=b"{}\n",
            )
        )


def test__reference_evidence_projection__rejects_audit_mismatch(
    reference_evidence_projection_fixture: ReferenceEvidenceProjectionFixture,
) -> None:
    request = reference_evidence_projection_fixture.complete_request()

    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="derivation-audit artifact does not match",
    ):
        ReferenceEvidenceProjectionActionizer().action(
            request=replace(request, derivation_audit_artifact=b"{}\n")
        )


def test__reference_evidence_projection__rejects_source_mismatch(
    reference_evidence_projection_fixture: ReferenceEvidenceProjectionFixture,
) -> None:
    request = reference_evidence_projection_fixture.complete_request()
    foreign = reference_evidence_projection_fixture.complete_request(
        source_bytes=b"different sanitized fixture source\n"
    )

    with pytest.raises(
        ReferenceEvidenceVerificationError,
        match="clean transcript does not match extraction source bytes",
    ):
        ReferenceEvidenceProjectionActionizer().action(
            request=replace(
                request,
                clean_transcript=foreign.clean_transcript,
                clean_transcript_result_bytes=(
                    foreign.clean_transcript_result_bytes
                ),
            )
        )
