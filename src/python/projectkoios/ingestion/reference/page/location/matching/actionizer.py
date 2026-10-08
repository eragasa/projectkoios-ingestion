"""Deterministic reference page-location matching action."""

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.reference.page.location.definition import (
    REFERENCE_LOCATOR_CONTRACT_VERSION,
    REFERENCE_LOCATOR_PROCESSOR_NAME,
    REFERENCE_LOCATOR_PROCESSOR_VERSION,
)
from projectkoios.ingestion.reference.page.location.error import (
    ReferenceLocatorVerificationError,
)
from projectkoios.ingestion.reference.page.location.identity import (
    ReferencePageLocatorResultIdentityDerivation,
)
from projectkoios.ingestion.reference.page.location.matching.request import (
    ReferencePageLocationRequest,
)
from projectkoios.ingestion.reference.page.location.result import (
    REFERENCE_PAGE_LOCATION_LIMITATIONS,
    ReferencePageLocatorResult,
)
from projectkoios.ingestion.reference.page.location.status import (
    ReferencePageLocatorStatus,
)
from projectkoios.ingestion.reference.page.location.verification import (
    ReferencePageEvidenceVerifier,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


class ReferencePageLocationActionizer(
    DataObjectActionizer[
        ReferencePageLocationRequest,
        ReferencePageLocatorResult,
    ]
):
    """Match complete token phrases over one exact clean-transcript page."""

    __slots__ = ()

    def action(
        self,
        *,
        request: ReferencePageLocationRequest,
    ) -> ReferencePageLocatorResult:
        """Return payload-free mechanical navigation evidence."""
        if type(request) is not ReferencePageLocationRequest:
            raise TypeError("request must be ReferencePageLocationRequest")
        locator = request.locator
        page = ReferencePageEvidenceVerifier(
            record=request.record,
            transcript=request.transcript,
        ).page(
            page_id=locator.page_id,
            page_index=locator.page_index,
        )
        if (
            locator.reference_evidence_record_id != request.record.record_id
            or locator.transcript_result_id != request.transcript.result_id
        ):
            raise ReferenceLocatorVerificationError(
                "locator does not match supplied evidence"
            )
        anchor_match = locator.topic_anchor_alternatives.match(page.text)
        encoded = page.text.encode("utf-8")
        digest = SHA256Fingerprinter.fingerprint(content=encoded)
        status = (
            ReferencePageLocatorStatus.MATCH
            if anchor_match.matched_identities
            else ReferencePageLocatorStatus.NO_MATCH
        )
        result_id = ReferencePageLocatorResultIdentityDerivation(
            locator_id=locator.locator_id,
            reference_evidence_record_id=(locator.reference_evidence_record_id),
            transcript_result_id=locator.transcript_result_id,
            page_id=locator.page_id,
            page_index=locator.page_index,
            topic_anchor_identities=anchor_match.all_identities,
            page_text_sha256=digest,
            page_text_utf8_byte_length=len(encoded),
            matched_topic_anchor_identities=(anchor_match.matched_identities),
            unmatched_topic_anchor_identities=(
                anchor_match.unmatched_identities
            ),
            status=status,
            limitations=REFERENCE_PAGE_LOCATION_LIMITATIONS,
            processor_name=REFERENCE_LOCATOR_PROCESSOR_NAME,
            processor_version=REFERENCE_LOCATOR_PROCESSOR_VERSION,
            contract_version=REFERENCE_LOCATOR_CONTRACT_VERSION,
        ).value
        return ReferencePageLocatorResult(
            result_id=result_id,
            locator_id=locator.locator_id,
            reference_evidence_record_id=(locator.reference_evidence_record_id),
            transcript_result_id=locator.transcript_result_id,
            page_id=locator.page_id,
            page_index=locator.page_index,
            topic_anchor_identities=anchor_match.all_identities,
            page_text_sha256=digest,
            page_text_utf8_byte_length=len(encoded),
            matched_topic_anchor_identities=(anchor_match.matched_identities),
            unmatched_topic_anchor_identities=(
                anchor_match.unmatched_identities
            ),
            status=status,
        )
