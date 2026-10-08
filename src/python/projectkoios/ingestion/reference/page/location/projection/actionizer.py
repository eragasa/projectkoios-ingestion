"""Deterministic reference page-locator projection action."""

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.reference.page.location.definition import (
    REFERENCE_LOCATOR_CONTRACT_VERSION,
)
from projectkoios.ingestion.reference.page.location.error import (
    ReferenceLocatorVerificationError,
)
from projectkoios.ingestion.reference.page.location.identity import (
    ReferencePageLocatorIdentityDerivation,
)
from projectkoios.ingestion.reference.page.location.locator import (
    ReferencePageLocator,
)
from projectkoios.ingestion.reference.page.location.projection.request import (
    ReferencePageLocatorProjectionRequest,
)
from projectkoios.ingestion.reference.page.location.verification import (
    ReferencePageEvidenceVerifier,
)


class ReferencePageLocatorProjectionActionizer(
    DataObjectActionizer[
        ReferencePageLocatorProjectionRequest,
        ReferencePageLocator,
    ]
):
    """Project one locator after exact lineage and page verification."""

    __slots__ = ()

    def action(
        self,
        *,
        request: ReferencePageLocatorProjectionRequest,
    ) -> ReferencePageLocator:
        """Return one deterministic bounded page locator."""
        if type(request) is not ReferencePageLocatorProjectionRequest:
            raise TypeError(
                "request must be ReferencePageLocatorProjectionRequest"
            )
        matches = tuple(
            page
            for page in request.transcript.pages
            if page.page_index == request.page_index
        )
        if len(matches) != 1:
            raise ReferenceLocatorVerificationError(
                "page_index does not identify one transcript page"
            )
        page = ReferencePageEvidenceVerifier(
            record=request.record,
            transcript=request.transcript,
        ).page(
            page_id=matches[0].page_id,
            page_index=request.page_index,
        )
        locator_id = ReferencePageLocatorIdentityDerivation(
            reference_evidence_record_id=request.record.record_id,
            transcript_result_id=request.transcript.result_id,
            page_id=page.page_id,
            page_index=page.page_index,
            topic_anchors=request.topic_anchor_alternatives,
            contract_version=REFERENCE_LOCATOR_CONTRACT_VERSION,
        ).value
        return ReferencePageLocator(
            locator_id=locator_id,
            reference_evidence_record_id=request.record.record_id,
            transcript_result_id=request.transcript.result_id,
            page_id=page.page_id,
            page_index=page.page_index,
            topic_anchor_alternatives=request.topic_anchor_alternatives,
        )
