"""Payload-free claim candidates over exact reference-page evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.reference_evidence import (
    ReferenceEvidenceRecord,
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference_locator import (
    REFERENCE_LOCATOR_MAX_ANCHORS,
    REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS,
    ReferencePageLocatorResult,
    ReferencePageLocatorStatus,
)

REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID = (
    "projectkoios.ingestion.reference-claim-candidate"
)
REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION = "0.1.0"
_REFERENCE_RECORD_ID = re.compile(
    r"reference-evidence-record:sha256:[0-9a-f]{64}"
)
_LOCATOR_RESULT_ID = re.compile(
    r"reference-page-locator-result:sha256:[0-9a-f]{64}"
)
_CANDIDATE_ID = re.compile(r"reference-claim-candidate:sha256:[0-9a-f]{64}")
_CLAIM_ID = re.compile(r"research-claim:sha256:[0-9a-f]{64}")
_BLOB_ID = re.compile(r"blob:sha256:([0-9a-f]{64})")
_TRANSCRIPT_ID = re.compile(r"clean-transcript-artifact:sha256:[0-9a-f]{64}")
_PAGE_ID = re.compile(r"clean-transcript-page:sha256:[0-9a-f]{64}")
_ANCHOR_ID = re.compile(r"reference-topic-anchor:sha256:[0-9a-f]{64}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_LIMITATIONS = (
    "automated_unreviewed",
    "citation_candidate_only",
    "manual_claim_review_required",
    "not_claim_support",
    "not_human_proofread",
    "not_publication_suitable",
    "not_scientifically_validated",
)


class ReferenceClaimCandidateError(ValueError):
    """Base failure for a bounded reference claim candidate."""


class ReferenceClaimCandidateVerificationError(ReferenceClaimCandidateError):
    """Raised when candidate inputs do not form one exact evidence lineage."""


class ReferenceClaimCandidateStatus(StrEnum):
    """Closed candidate status; acceptance and publication are absent."""

    MANUAL_REVIEW_REQUIRED = "manual_review_required"


def _identity(value: object, pattern: re.Pattern[str], field: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"{field} has an invalid identity grammar")
    return value


@dataclass(frozen=True, slots=True)
class ReferenceClaimCandidate:
    """Bind one external claim identity to mechanical page evidence."""

    candidate_id: str
    claim_identity: str
    reference_evidence_record_id: str
    locator_result_id: str
    source_blob_id: str
    source_content_sha256: str
    transcript_artifact_id: str
    page_id: str
    page_index: int
    page_text_sha256: str
    page_text_utf8_byte_length: int
    matched_topic_anchor_identities: tuple[str, ...]
    status: ReferenceClaimCandidateStatus = (
        ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED
    )
    limitations: tuple[str, ...] = _LIMITATIONS
    contract_id: str = REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID
    contract_version: str = REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        record: ReferenceEvidenceRecord,
        locator_result: ReferencePageLocatorResult,
        claim_identity: str,
    ) -> ReferenceClaimCandidate:
        """Create a candidate from a verified record and positive locator."""
        if type(record) is not ReferenceEvidenceRecord:
            raise TypeError("record must be ReferenceEvidenceRecord")
        if type(locator_result) is not ReferencePageLocatorResult:
            raise TypeError("locator_result must be ReferencePageLocatorResult")
        try:
            record.require_reusable()
        except ReferenceEvidenceVerificationError as error:
            raise ReferenceClaimCandidateVerificationError(
                "reference evidence is not reusable"
            ) from error
        claim = _identity(claim_identity, _CLAIM_ID, "claim_identity")
        if locator_result.status is not ReferencePageLocatorStatus.MATCH:
            raise ReferenceClaimCandidateVerificationError(
                "a claim candidate requires a positive page match"
            )
        if (
            locator_result.reference_evidence_record_id != record.record_id
            or locator_result.transcript_artifact_id
            != record.transcript.artifact_id
        ):
            raise ReferenceClaimCandidateVerificationError(
                "locator result does not match reference-evidence lineage"
            )
        candidate_id = stable_id(
            "reference-claim-candidate",
            claim,
            record.record_id,
            locator_result.result_id,
            record.source.blob_id,
            record.source.content_sha256,
            locator_result.transcript_artifact_id,
            locator_result.page_id,
            locator_result.page_index,
            locator_result.page_text_sha256,
            locator_result.page_text_utf8_byte_length,
            locator_result.matched_topic_anchor_identities,
            ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED,
            _LIMITATIONS,
            REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID,
            REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION,
        )
        return cls(
            candidate_id,
            claim,
            record.record_id,
            locator_result.result_id,
            record.source.blob_id,
            record.source.content_sha256,
            locator_result.transcript_artifact_id,
            locator_result.page_id,
            locator_result.page_index,
            locator_result.page_text_sha256,
            locator_result.page_text_utf8_byte_length,
            locator_result.matched_topic_anchor_identities,
        )

    def __post_init__(self) -> None:
        _identity(self.candidate_id, _CANDIDATE_ID, "candidate_id")
        _identity(self.claim_identity, _CLAIM_ID, "claim_identity")
        _identity(
            self.reference_evidence_record_id,
            _REFERENCE_RECORD_ID,
            "reference_evidence_record_id",
        )
        _identity(
            self.locator_result_id,
            _LOCATOR_RESULT_ID,
            "locator_result_id",
        )
        source_blob_id = _identity(
            self.source_blob_id,
            _BLOB_ID,
            "source_blob_id",
        )
        source_digest = _identity(
            self.source_content_sha256,
            _SHA256,
            "source_content_sha256",
        )
        if source_blob_id != f"blob:sha256:{source_digest}":
            raise ValueError("source blob identity must bind source digest")
        _identity(
            self.transcript_artifact_id,
            _TRANSCRIPT_ID,
            "transcript_artifact_id",
        )
        _identity(self.page_id, _PAGE_ID, "page_id")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        _identity(
            self.page_text_sha256,
            _SHA256,
            "page_text_sha256",
        )
        if (
            type(self.page_text_utf8_byte_length) is not int
            or self.page_text_utf8_byte_length < 0
            or self.page_text_utf8_byte_length
            > REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS * 4
        ):
            raise ValueError("page text byte length is outside its bound")
        anchors = self.matched_topic_anchor_identities
        if (
            type(anchors) is not tuple
            or not anchors
            or anchors != tuple(sorted(anchors))
            or len(anchors) != len(set(anchors))
            or len(anchors) > REFERENCE_LOCATOR_MAX_ANCHORS
            or any(
                type(anchor) is not str or _ANCHOR_ID.fullmatch(anchor) is None
                for anchor in anchors
            )
        ):
            raise ValueError(
                "matched topic anchors must be a bounded identity tuple"
            )
        if self.status is not (
            ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED
        ):
            raise ValueError("unsupported reference claim candidate status")
        if self.limitations != _LIMITATIONS:
            raise ValueError(
                "reference claim candidate limitations are incomplete"
            )
        if self.contract_id != REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID:
            raise ValueError(
                "unsupported reference claim candidate contract ID"
            )
        if self.contract_version != (
            REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION
        ):
            raise ValueError("unsupported reference claim candidate contract")
        expected = stable_id(
            "reference-claim-candidate",
            self.claim_identity,
            self.reference_evidence_record_id,
            self.locator_result_id,
            self.source_blob_id,
            self.source_content_sha256,
            self.transcript_artifact_id,
            self.page_id,
            self.page_index,
            self.page_text_sha256,
            self.page_text_utf8_byte_length,
            self.matched_topic_anchor_identities,
            self.status,
            self.limitations,
            self.contract_id,
            self.contract_version,
        )
        if self.candidate_id != expected:
            raise ValueError(
                "reference claim candidate identity is inconsistent"
            )
