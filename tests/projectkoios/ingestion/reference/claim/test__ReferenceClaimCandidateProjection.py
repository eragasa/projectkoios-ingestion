"""Verification for payload-free reference claim-candidate projection."""

from dataclasses import fields, replace

import pytest
from projectkoios.ingestion.reference.claim.error import (
    ReferenceClaimCandidateVerificationError,
)
from projectkoios.ingestion.reference.claim.identity import (
    ResearchClaimIdentity,
)
from projectkoios.ingestion.reference.claim.projection.actionizer import (
    ReferenceClaimCandidateProjectionActionizer,
)
from projectkoios.ingestion.reference.claim.projection.request import (
    ReferenceClaimCandidateProjectionRequest,
)
from projectkoios.ingestion.reference.claim.status import (
    ReferenceClaimCandidateStatus,
)
from projectkoios.ingestion.reference.page.location.matching.actionizer import (
    ReferencePageLocationActionizer,
)
from projectkoios.ingestion.reference.page.location.matching.request import (
    ReferencePageLocationRequest,
)
from projectkoios.ingestion.reference.page.location.projection.actionizer import (  # noqa: E501
    ReferencePageLocatorProjectionActionizer,
)
from projectkoios.ingestion.reference.page.location.projection.request import (
    ReferencePageLocatorProjectionRequest,
)
from projectkoios.ingestion.reference.page.location.status import (
    ReferencePageLocatorStatus,
)

from tests.projectkoios.ingestion.reference.claim.fixture import (
    ReferenceClaimCandidateFixture,
)
from tests.projectkoios.ingestion.reference.evidence.fixture.record import (
    ReferenceEvidenceRecordFixture,
)
from tests.projectkoios.ingestion.reference.page.location.fixture import (
    ReferencePageLocationFixture,
)

_CLAIM_ID = ResearchClaimIdentity(f"research-claim:sha256:{'f' * 64}")


def test__reference_claim_candidate__binds_exact_payload_free_evidence(
    reference_claim_candidate_fixture: ReferenceClaimCandidateFixture,
) -> None:
    record, _, result = reference_claim_candidate_fixture.inputs()

    candidate = ReferenceClaimCandidateProjectionActionizer().action(
        request=ReferenceClaimCandidateProjectionRequest(
            record=record,
            locator_result=result,
            claim_identity=_CLAIM_ID,
        )
    )

    assert candidate.status is (
        ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED
    )
    assert candidate.candidate_id == (
        "reference-claim-candidate:sha256:"
        "798ca82241a9a61470bd585458736a5e5f7330e59ab89e6db04dba9933608c58"
    )
    assert result.result_id == (
        "reference-page-locator-result:sha256:"
        "7f449974972e56701a4e4e6d9039116300e8b9dcb3e0eb7a144206affeef9d35"
    )
    assert candidate.claim_identity == _CLAIM_ID
    assert candidate.reference_evidence_record_id == record.record_id
    assert candidate.locator_result_id == result.result_id
    assert candidate.page_text_sha256 == result.page_text_sha256
    assert (
        candidate.matched_topic_anchor_identities
        == result.matched_topic_anchor_identities
    )
    assert all(
        word not in {field.name for field in fields(candidate)}
        for word in (
            "authority",
            "claim_text",
            "page_text",
            "publication",
            "quotation",
            "source_path",
        )
    )
    assert "effective mass" not in repr(candidate)


def test__reference_claim_candidate__preserves_historical_identity(
    reference_page_location_fixture: ReferencePageLocationFixture,
) -> None:
    record, transcript = reference_page_location_fixture.evidence()
    locator = ReferencePageLocatorProjectionActionizer().action(
        request=ReferencePageLocatorProjectionRequest(
            record=record,
            transcript=transcript,
            page_index=0,
            topic_anchor_alternatives=(
                reference_page_location_fixture.anchors("effective mass")
            ),
        )
    )
    result = ReferencePageLocationActionizer().action(
        request=ReferencePageLocationRequest(
            record=record,
            transcript=transcript,
            locator=locator,
        )
    )

    candidate = ReferenceClaimCandidateProjectionActionizer().action(
        request=ReferenceClaimCandidateProjectionRequest(
            record=record,
            locator_result=result,
            claim_identity=_CLAIM_ID,
        )
    )

    assert candidate.candidate_id == (
        "reference-claim-candidate:sha256:"
        "9dd1e00170caa02b1ecf071294239bb4af3f4d0fae5ba14aed8d94aff1df5950"
    )


def test__reference_claim_candidate__requires_typed_request() -> None:
    with pytest.raises(
        TypeError,
        match="request must be ReferenceClaimCandidateProjectionRequest",
    ):
        ReferenceClaimCandidateProjectionActionizer().action(
            request=object()  # type: ignore[arg-type]
        )


def test__reference_claim_candidate__requires_typed_claim_identity(
    reference_claim_candidate_fixture: ReferenceClaimCandidateFixture,
) -> None:
    record, _, result = reference_claim_candidate_fixture.inputs()

    with pytest.raises(TypeError, match="ResearchClaimIdentity"):
        ReferenceClaimCandidateProjectionRequest(
            record=record,
            locator_result=result,
            claim_identity=_CLAIM_ID.value,  # type: ignore[arg-type]
        )


def test__reference_claim_candidate__rejects_invalid_claim_identity() -> None:
    with pytest.raises(ValueError, match="research claim identity"):
        ResearchClaimIdentity("claim:unbounded")


def test__reference_claim_candidate__rejects_incomplete_evidence(
    reference_claim_candidate_fixture: ReferenceClaimCandidateFixture,
    reference_evidence_record_fixture: ReferenceEvidenceRecordFixture,
) -> None:
    record, _, result = reference_claim_candidate_fixture.inputs()
    incomplete = reference_evidence_record_fixture.incomplete_record(
        original=record,
        reason="fixture_incomplete",
    )

    with pytest.raises(
        ReferenceClaimCandidateVerificationError,
        match="reference evidence is not reusable",
    ):
        ReferenceClaimCandidateProjectionActionizer().action(
            request=ReferenceClaimCandidateProjectionRequest(
                record=incomplete,
                locator_result=result,
                claim_identity=_CLAIM_ID,
            )
        )


def test__reference_claim_candidate__rejects_no_match(
    reference_claim_candidate_fixture: ReferenceClaimCandidateFixture,
) -> None:
    record, _, result = reference_claim_candidate_fixture.inputs(
        page_text="A biomass model is discussed.",
        topic_anchor_alternatives=("mass",),
    )
    assert result.status is ReferencePageLocatorStatus.NO_MATCH

    with pytest.raises(
        ReferenceClaimCandidateVerificationError,
        match="positive page match",
    ):
        ReferenceClaimCandidateProjectionActionizer().action(
            request=ReferenceClaimCandidateProjectionRequest(
                record=record,
                locator_result=result,
                claim_identity=_CLAIM_ID,
            )
        )


def test__reference_claim_candidate__rejects_cross_source(
    reference_claim_candidate_fixture: ReferenceClaimCandidateFixture,
) -> None:
    record, _, result = reference_claim_candidate_fixture.inputs()
    other_record, _, _ = reference_claim_candidate_fixture.inputs(
        source_bytes=b"different claim fixture source\n"
    )

    with pytest.raises(
        ReferenceClaimCandidateVerificationError,
        match="lineage",
    ):
        ReferenceClaimCandidateProjectionActionizer().action(
            request=ReferenceClaimCandidateProjectionRequest(
                record=other_record,
                locator_result=result,
                claim_identity=_CLAIM_ID,
            )
        )


def test__reference_claim_candidate__rejects_identity_tampering(
    reference_claim_candidate_fixture: ReferenceClaimCandidateFixture,
) -> None:
    record, _, result = reference_claim_candidate_fixture.inputs()
    candidate = ReferenceClaimCandidateProjectionActionizer().action(
        request=ReferenceClaimCandidateProjectionRequest(
            record=record,
            locator_result=result,
            claim_identity=_CLAIM_ID,
        )
    )

    with pytest.raises(ValueError, match="identity is inconsistent"):
        replace(
            candidate,
            candidate_id=f"reference-claim-candidate:sha256:{'0' * 64}",
        )
