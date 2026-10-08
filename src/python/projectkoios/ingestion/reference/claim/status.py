"""Closed reference claim-candidate status."""

from enum import StrEnum


class ReferenceClaimCandidateStatus(StrEnum):
    """Candidate status that requires manual review without acceptance."""

    MANUAL_REVIEW_REQUIRED = "manual_review_required"
