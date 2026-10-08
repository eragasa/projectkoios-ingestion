"""Deterministic reference claim-candidate projection action."""

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.reference.claim.candidate import (
    ReferenceClaimCandidate,
)
from projectkoios.ingestion.reference.claim.definition import (
    REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID,
    REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION,
)
from projectkoios.ingestion.reference.claim.error import (
    ReferenceClaimCandidateVerificationError,
)
from projectkoios.ingestion.reference.claim.identity import (
    ReferenceClaimCandidateIdentityDerivation,
)
from projectkoios.ingestion.reference.claim.limitation import (
    REFERENCE_CLAIM_CANDIDATE_LIMITATIONS,
)
from projectkoios.ingestion.reference.claim.projection.request import (
    ReferenceClaimCandidateProjectionRequest,
)
from projectkoios.ingestion.reference.claim.status import (
    ReferenceClaimCandidateStatus,
)
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.page.location.status import (
    ReferencePageLocatorStatus,
)


class ReferenceClaimCandidateProjectionActionizer(
    DataObjectActionizer[
        ReferenceClaimCandidateProjectionRequest,
        ReferenceClaimCandidate,
    ]
):
    """Project one payload-free candidate from exact positive evidence."""

    __slots__ = ()

    def action(
        self,
        *,
        request: ReferenceClaimCandidateProjectionRequest,
    ) -> ReferenceClaimCandidate:
        """Return one deterministic manual-review candidate."""
        if type(request) is not ReferenceClaimCandidateProjectionRequest:
            raise TypeError(
                "request must be ReferenceClaimCandidateProjectionRequest"
            )
        record = request.record
        locator_result = request.locator_result
        try:
            record.require_reusable()
        except ReferenceEvidenceVerificationError as error:
            raise ReferenceClaimCandidateVerificationError(
                "reference evidence is not reusable"
            ) from error
        if locator_result.status is not ReferencePageLocatorStatus.MATCH:
            raise ReferenceClaimCandidateVerificationError(
                "a claim candidate requires a positive page match"
            )
        if (
            locator_result.reference_evidence_record_id != record.record_id
            or locator_result.transcript_result_id
            != record.transcript.result_id
        ):
            raise ReferenceClaimCandidateVerificationError(
                "locator result does not match reference-evidence lineage"
            )
        status = ReferenceClaimCandidateStatus.MANUAL_REVIEW_REQUIRED
        candidate_id = ReferenceClaimCandidateIdentityDerivation(
            claim_identity=request.claim_identity,
            reference_evidence_record_id=record.record_id,
            locator_result_id=locator_result.result_id,
            source_blob_id=record.source.blob_id,
            source_content_sha256=record.source.content_sha256,
            transcript_result_id=locator_result.transcript_result_id,
            page_id=locator_result.page_id,
            page_index=locator_result.page_index,
            page_text_sha256=locator_result.page_text_sha256,
            page_text_utf8_byte_length=(
                locator_result.page_text_utf8_byte_length
            ),
            matched_topic_anchor_identities=(
                locator_result.matched_topic_anchor_identities
            ),
            status=status,
            limitations=REFERENCE_CLAIM_CANDIDATE_LIMITATIONS,
            contract_id=REFERENCE_CLAIM_CANDIDATE_CONTRACT_ID,
            contract_version=REFERENCE_CLAIM_CANDIDATE_CONTRACT_VERSION,
        ).value
        return ReferenceClaimCandidate(
            candidate_id=candidate_id,
            claim_identity=request.claim_identity,
            reference_evidence_record_id=record.record_id,
            locator_result_id=locator_result.result_id,
            source_blob_id=record.source.blob_id,
            source_content_sha256=record.source.content_sha256,
            transcript_result_id=locator_result.transcript_result_id,
            page_id=locator_result.page_id,
            page_index=locator_result.page_index,
            page_text_sha256=locator_result.page_text_sha256,
            page_text_utf8_byte_length=(
                locator_result.page_text_utf8_byte_length
            ),
            matched_topic_anchor_identities=(
                locator_result.matched_topic_anchor_identities
            ),
            status=status,
        )
