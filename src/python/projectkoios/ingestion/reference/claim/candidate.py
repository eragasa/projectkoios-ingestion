"""Immutable payload-free reference claim-candidate action result."""

import re
from dataclasses import dataclass

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.reference.claim.definition import (
    REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID,
    REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION,
)
from projectkoios.ingestion.reference.claim.identity import (
    ReferenceClaimCandidateIdentityDerivation,
    ResearchClaimIdentity,
)
from projectkoios.ingestion.reference.claim.limitation import (
    REFERENCE_CLAIM_CANDIDATE_LIMITATIONS,
    ReferenceClaimCandidateLimitations,
)
from projectkoios.ingestion.reference.claim.status import (
    ReferenceClaimCandidateStatus,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorIdentityInventory,
)

_CANDIDATE_ID = re.compile(r"reference-claim-candidate:sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ReferenceClaimCandidate(AbstractDataObjectActionResult):
    """Bind one external claim identity to mechanical page evidence."""

    candidate_id: str
    claim_identity: ResearchClaimIdentity
    reference_evidence_record_id: str
    locator_result_id: str
    source_blob_id: str
    source_content_sha256: str
    transcript_result_id: str
    page_id: str
    page_index: int
    page_text_sha256: str
    page_text_utf8_byte_length: int
    matched_topic_anchor_identities: ReferenceTopicAnchorIdentityInventory
    status: ReferenceClaimCandidateStatus = (
        ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED
    )
    limitations: ReferenceClaimCandidateLimitations = (
        REFERENCE_CLAIM_CANDIDATE_LIMITATIONS
    )
    contract_id: str = REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID
    contract_version: str = REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            type(self.candidate_id) is not str
            or _CANDIDATE_ID.fullmatch(self.candidate_id) is None
        ):
            raise ValueError("candidate_id has an invalid identity grammar")
        expected = ReferenceClaimCandidateIdentityDerivation(
            claim_identity=self.claim_identity,
            reference_evidence_record_id=self.reference_evidence_record_id,
            locator_result_id=self.locator_result_id,
            source_blob_id=self.source_blob_id,
            source_content_sha256=self.source_content_sha256,
            transcript_result_id=self.transcript_result_id,
            page_id=self.page_id,
            page_index=self.page_index,
            page_text_sha256=self.page_text_sha256,
            page_text_utf8_byte_length=self.page_text_utf8_byte_length,
            matched_topic_anchor_identities=(
                self.matched_topic_anchor_identities
            ),
            status=self.status,
            limitations=self.limitations,
            contract_id=self.contract_id,
            contract_version=self.contract_version,
        ).value
        if self.candidate_id != expected:
            raise ValueError(
                "reference claim candidate identity is inconsistent"
            )
