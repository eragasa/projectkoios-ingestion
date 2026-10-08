"""Immutable request for reference page-locator projection."""

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.clean_transcript import CleanTranscript
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.page.location.inventory import (
    ReferenceTopicAnchorInventory,
)


@dataclass(frozen=True, slots=True)
class ReferencePageLocatorProjectionRequest(DataObjectActionRequest):
    """Bind exact evidence, transcript, page index, and topic anchors."""

    record: ReferenceEvidenceRecord
    transcript: CleanTranscript
    page_index: int
    topic_anchor_alternatives: ReferenceTopicAnchorInventory

    def __post_init__(self) -> None:
        if type(self.record) is not ReferenceEvidenceRecord:
            raise TypeError("record must be ReferenceEvidenceRecord")
        if type(self.transcript) is not CleanTranscript:
            raise TypeError("transcript must be CleanTranscript")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page_index must be a nonnegative built-in int")
        if (
            type(self.topic_anchor_alternatives)
            is not ReferenceTopicAnchorInventory
        ):
            raise TypeError(
                "topic anchors must be ReferenceTopicAnchorInventory"
            )
