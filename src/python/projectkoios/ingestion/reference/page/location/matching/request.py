"""Immutable request for reference page-location matching."""

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.clean_transcript import CleanTranscript
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.page.location.locator import (
    ReferencePageLocator,
)


@dataclass(frozen=True, slots=True)
class ReferencePageLocationRequest(DataObjectActionRequest):
    """Bind exact evidence, transcript, and one page locator."""

    record: ReferenceEvidenceRecord
    transcript: CleanTranscript
    locator: ReferencePageLocator

    def __post_init__(self) -> None:
        if type(self.record) is not ReferenceEvidenceRecord:
            raise TypeError("record must be ReferenceEvidenceRecord")
        if type(self.transcript) is not CleanTranscript:
            raise TypeError("transcript must be CleanTranscript")
        if type(self.locator) is not ReferencePageLocator:
            raise TypeError("locator must be ReferencePageLocator")
