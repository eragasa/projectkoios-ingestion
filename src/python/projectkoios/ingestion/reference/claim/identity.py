"""Typed claim identity and bounded candidate identity derivation."""

import re
from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.reference.claim.definition import (
    REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID,
    REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION,
)
from projectkoios.ingestion.reference.claim.limitation import (
    ReferenceClaimCandidateLimitations,
)
from projectkoios.ingestion.reference.claim.status import (
    ReferenceClaimCandidateStatus,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorIdentityInventory,
)
from projectkoios.ingestion.reference.page.location.limits.definition import (
    REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

_RESEARCH_CLAIM_ID = re.compile(r"research-claim:sha256:[0-9a-f]{64}")
_REFERENCE_RECORD_ID = re.compile(
    r"reference-evidence-record:sha256:[0-9a-f]{64}"
)
_LOCATOR_RESULT_ID = re.compile(
    r"reference-page-locator-result:sha256:[0-9a-f]{64}"
)
_BLOB_ID = re.compile(r"blob:sha256:[0-9a-f]{64}")
_TRANSCRIPT_ID = re.compile(r"clean-transcript-result:sha256:[0-9a-f]{64}")
_PAGE_ID = re.compile(r"clean-transcript-page:sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ResearchClaimIdentity:
    """One syntax-validated external research-claim identity reference."""

    value: str

    def __post_init__(self) -> None:
        if (
            type(self.value) is not str
            or _RESEARCH_CLAIM_ID.fullmatch(self.value) is None
        ):
            raise ValueError("research claim identity has invalid grammar")


@dataclass(frozen=True, slots=True)
class ReferenceClaimCandidateIdentityDerivation:
    """Validated ordered input to one stable claim-candidate identity."""

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
    status: ReferenceClaimCandidateStatus
    limitations: ReferenceClaimCandidateLimitations
    contract_id: str
    contract_version: str

    def __post_init__(self) -> None:
        if type(self.claim_identity) is not ResearchClaimIdentity:
            raise TypeError("claim_identity must be ResearchClaimIdentity")
        for value, pattern, field in (
            (
                self.reference_evidence_record_id,
                _REFERENCE_RECORD_ID,
                "reference_evidence_record_id",
            ),
            (self.locator_result_id, _LOCATOR_RESULT_ID, "locator_result_id"),
            (self.source_blob_id, _BLOB_ID, "source_blob_id"),
            (self.transcript_result_id, _TRANSCRIPT_ID, "transcript_result_id"),
            (self.page_id, _PAGE_ID, "page_id"),
        ):
            if type(value) is not str or pattern.fullmatch(value) is None:
                raise ValueError(f"{field} has an invalid identity grammar")
        if not SHA256Hash.is_canonical(self.source_content_sha256):
            raise ValueError("source_content_sha256 has an invalid grammar")
        if self.source_blob_id != f"blob:sha256:{self.source_content_sha256}":
            raise ValueError("source blob identity must bind source digest")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        if not SHA256Hash.is_canonical(self.page_text_sha256):
            raise ValueError("page_text_sha256 has an invalid grammar")
        if (
            type(self.page_text_utf8_byte_length) is not int
            or self.page_text_utf8_byte_length < 0
            or self.page_text_utf8_byte_length
            > REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS * 4
        ):
            raise ValueError("page text byte length is outside its bound")
        if (
            type(self.matched_topic_anchor_identities)
            is not ReferenceTopicAnchorIdentityInventory
            or not self.matched_topic_anchor_identities
        ):
            raise ValueError(
                "matched topic anchors require a nonempty identity inventory"
            )
        if self.status is not (
            ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED
        ):
            raise ValueError("unsupported reference claim candidate status")
        if type(self.limitations) is not ReferenceClaimCandidateLimitations:
            raise TypeError(
                "limitations must be ReferenceClaimCandidateLimitations"
            )
        if self.contract_id != REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID:
            raise ValueError(
                "unsupported reference claim candidate contract ID"
            )
        if self.contract_version != (
            REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION
        ):
            raise ValueError("unsupported reference claim candidate contract")

    @property
    def value(self) -> str:
        """Return the stable candidate identifier from validated values."""
        return stable_id(
            "reference-claim-candidate",
            self.claim_identity.value,
            self.reference_evidence_record_id,
            self.locator_result_id,
            self.source_blob_id,
            self.source_content_sha256,
            self.transcript_result_id,
            self.page_id,
            self.page_index,
            self.page_text_sha256,
            self.page_text_utf8_byte_length,
            tuple(self.matched_topic_anchor_identities),
            self.status,
            tuple(item.value for item in self.limitations),
            self.contract_id,
            self.contract_version,
        )
