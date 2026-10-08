"""Immutable fixture owner for reference claim-candidate projection."""

from dataclasses import dataclass

from projectkoios.ingestion.clean_transcript import CleanTranscript
from projectkoios.ingestion.reference.evidence.projection.actionizer import (
    ReferenceEvidenceProjectionActionizer,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.page.location.anchor import (
    ReferenceTopicAnchor,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorInventory,
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
from projectkoios.ingestion.reference.page.location.result import (
    ReferencePageLocatorResult,
)

from tests.projectkoios.ingestion.reference.evidence.fixture.projection import (
    ReferenceEvidenceProjectionFixture,
)


@dataclass(frozen=True, slots=True)
class ReferenceClaimCandidateFixture:
    """Build exact reusable evidence and one deterministic locator result."""

    evidence_fixture: ReferenceEvidenceProjectionFixture

    def inputs(
        self,
        *,
        source_bytes: bytes | None = None,
        page_text: str = "The effective-mass model includes decay.",
        topic_anchor_alternatives: tuple[str, ...] = ("effective mass",),
    ) -> tuple[
        ReferenceEvidenceRecord,
        CleanTranscript,
        ReferencePageLocatorResult,
    ]:
        projection_request = self.evidence_fixture.complete_request(
            source_bytes=source_bytes,
            page_text=page_text,
        )
        record = ReferenceEvidenceProjectionActionizer().action(
            request=projection_request
        )
        transcript = projection_request.clean_transcript
        locator = ReferencePageLocatorProjectionActionizer().action(
            request=ReferencePageLocatorProjectionRequest(
                record=record,
                transcript=transcript,
                page_index=0,
                topic_anchor_alternatives=ReferenceTopicAnchorInventory(
                    *(
                        ReferenceTopicAnchor(text)
                        for text in topic_anchor_alternatives
                    )
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
        return record, transcript, result
