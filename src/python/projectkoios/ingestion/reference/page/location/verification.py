"""State-bound exact reference page-lineage verification."""

from dataclasses import dataclass

from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    CleanTranscriptPage,
)
from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.record import (
    ReferenceEvidenceRecord,
)
from projectkoios.ingestion.reference.page.location.error import (
    ReferenceLocatorVerificationError,
)
from projectkoios.ingestion.reference.page.location.limits.definition import (
    REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS,
)
from projectkoios.ingestion.reference.page.location.limits.error import (
    ReferenceLocatorLimitError,
)


@dataclass(frozen=True, slots=True)
class ReferencePageEvidenceVerifier:
    """Bind one reusable evidence record and its exact clean transcript."""

    record: ReferenceEvidenceRecord
    transcript: CleanTranscript

    def __post_init__(self) -> None:
        if type(self.record) is not ReferenceEvidenceRecord:
            raise TypeError("record must be ReferenceEvidenceRecord")
        if type(self.transcript) is not CleanTranscript:
            raise TypeError("transcript must be CleanTranscript")
        try:
            self.record.require_reusable()
        except ReferenceEvidenceVerificationError as error:
            raise ReferenceLocatorVerificationError(
                "reference evidence is not reusable"
            ) from error
        if (
            self.record.transcript.result_id != self.transcript.result_id
            or self.record.transcript.structured_transcription_result_id
            != self.transcript.transcription_result_id
            or tuple(self.record.transcript.layout_result_ids)
            != self.transcript.layout_result_ids
            or self.record.transcript.text_sha256 != self.transcript.text_sha256
            or self.record.transcript.text_utf8_byte_length
            != self.transcript.utf8_byte_length
            or self.record.extraction.document_id != self.transcript.document_id
            or self.record.source.blob_id != self.transcript.source_blob_id
            or self.record.source.content_sha256
            != self.transcript.source_content_hash
        ):
            raise ReferenceLocatorVerificationError(
                "transcript does not match reference-evidence lineage"
            )

    def page(self, *, page_id: str, page_index: int) -> CleanTranscriptPage:
        """Return the uniquely identified bounded page."""
        matches = tuple(
            page
            for page in self.transcript.pages
            if page.page_id == page_id and page.page_index == page_index
        )
        if len(matches) != 1:
            raise ReferenceLocatorVerificationError(
                "locator page does not identify one transcript page"
            )
        page = matches[0]
        if len(page.text) > REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS:
            raise ReferenceLocatorLimitError(
                "transcript page exceeds text limit"
            )
        return page
