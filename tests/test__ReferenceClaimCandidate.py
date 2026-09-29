"""Verification for payload-free reference claim candidates."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest
from projectkoios.ingestion import (
    ReferenceClaimCandidate,
    ReferenceClaimCandidateStatus,
    ReferenceClaimCandidateVerificationError,
    ReferencePageLocator,
    ReferencePageLocatorChecker,
)
from test__ReferencePageLocator import evidence


def positive_evidence():
    record, transcript = evidence()
    locator = ReferencePageLocator.create(
        record=record,
        transcript=transcript,
        page_index=0,
        topic_anchor_alternatives=("effective mass",),
    )
    result = ReferencePageLocatorChecker().execute(
        record=record,
        transcript=transcript,
        locator=locator,
    )
    return record, transcript, result


def test__reference_claim_candidate__binds_exact_payload_free_evidence() -> (
    None
):
    record, _, result = positive_evidence()

    candidate = ReferenceClaimCandidate.create(
        record=record,
        locator_result=result,
        claim_identity=f"research-claim:sha256:{'f' * 64}",
    )

    assert candidate.status is (
        ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED
    )
    assert candidate.candidate_id == (
        "reference-claim-candidate:sha256:"
        "fd86bb918a76960c2a3106a5268dde230647ba62e1dc1e6001c5fdff927c0bdd"
    )
    assert result.result_id == (
        "reference-page-locator-result:sha256:"
        "b2fac7eb7a48e3682ea9b16107ab9b44399c048f0df881c94a070ac6cffd0cec"
    )
    assert candidate.reference_evidence_record_id == record.record_id
    assert candidate.locator_result_id == result.result_id
    assert candidate.page_text_sha256 == result.page_text_sha256
    assert candidate.matched_topic_anchor_identities == (
        result.matched_topic_anchor_identities
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


def test__reference_claim_candidate__rejects_no_match() -> None:
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

    with pytest.raises(
        ReferenceClaimCandidateVerificationError,
        match="positive page match",
    ):
        ReferenceClaimCandidate.create(
            record=record,
            locator_result=result,
            claim_identity=f"research-claim:sha256:{'f' * 64}",
        )


def test__reference_claim_candidate__rejects_cross_source_and_tampering() -> (
    None
):
    record, _, result = positive_evidence()
    other_record, _ = evidence(source_digest="b" * 64)

    with pytest.raises(
        ReferenceClaimCandidateVerificationError,
        match="lineage",
    ):
        ReferenceClaimCandidate.create(
            record=other_record,
            locator_result=result,
            claim_identity=f"research-claim:sha256:{'f' * 64}",
        )

    candidate = ReferenceClaimCandidate.create(
        record=record,
        locator_result=result,
        claim_identity=f"research-claim:sha256:{'f' * 64}",
    )
    with pytest.raises(ValueError, match="identity is inconsistent"):
        replace(
            candidate,
            candidate_id=f"reference-claim-candidate:sha256:{'0' * 64}",
        )
