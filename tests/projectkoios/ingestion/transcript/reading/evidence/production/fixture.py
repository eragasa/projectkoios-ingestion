"""Semantic test owner for current reading producer actions."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    DeterministicCleanTranscriptProjector,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.inventory import (  # noqa: E501
    ReadingPageTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.evidence import (
    ReadingTextStreamEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.basis import (  # noqa: E501
    ReadingTextSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.definition import (  # noqa: E501
    ReadingTextSelection,
)

from tests.clean_transcript_support import CleanTranscriptSourceFixture


@dataclass(frozen=True, slots=True)
class ReadingCurrentProducerFixture:
    """Own exact current sources and their typed page evidence."""

    source: CleanTranscriptSourceFixture
    transcript: CleanTranscript
    page_text: ReadingPageTextProducerEvidenceInventory

    @classmethod
    def build(
        cls,
        *,
        replacement_split: str | None = None,
    ) -> ReadingCurrentProducerFixture:
        """Build current producer sources with exact native page selections."""
        source = CleanTranscriptSourceFixture.build(
            replacement_split=replacement_split
        )
        transcript = DeterministicCleanTranscriptProjector().project(
            source.transcription,
            source.layouts,
        )
        pages: list[ReadingPageTextProducerEvidence] = []
        document = source.transcription.transcription_input.document
        for page in document.pages:
            location = ReadingPageLocation(
                physical_page_index=page.page_index,
                printed_page_label=page.printed_page_label,
            )
            stream = ReadingTextStreamEvidence(
                kind=ReadingTextStreamKind.NATIVE,
                page_location=location,
                text="\n".join(block.text or "" for block in page.blocks),
                upstream_id=ReadingEvidenceIdentity(
                    kind=ReadingEvidenceIdentityKind.EXTRACTION_RESULT,
                    value=source.transcription.result_id,
                ),
                producer_id=ReadingEvidenceIdentity(
                    kind=ReadingEvidenceIdentityKind.PRODUCER,
                    value="current-native-text-fixture",
                ),
                composition_id=None,
                automated=True,
                accepted=False,
                review_status=ReadingReviewStatus.UNREVIEWED,
            )
            streams = ReadingTextStreamEvidenceInventory(stream)
            selection = ReadingTextSelection(
                streams=streams,
                selected_stream_id=stream.stream_id,
                basis=ReadingTextSelectionBasis.NATIVE_EXACT,
            )
            pages.append(
                ReadingPageTextProducerEvidence(
                    streams=streams,
                    selection=selection,
                    producer_id=ReadingEvidenceIdentity(
                        kind=ReadingEvidenceIdentityKind.PRODUCER,
                        value="current-page-text-fixture",
                    ),
                    producer_version="1",
                    review_status=ReadingReviewStatus.UNREVIEWED,
                )
            )
        return cls(
            source=source,
            transcript=transcript,
            page_text=ReadingPageTextProducerEvidenceInventory(*pages),
        )
