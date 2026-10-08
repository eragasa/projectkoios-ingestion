"""Per-page native and OCR stream inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.evidence import (
    ReadingTextStreamEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingTextStreamEvidenceInventory:
    """Own one page's native and optional OCR stream evidence."""

    page_location: ReadingPageLocation
    _streams: tuple[ReadingTextStreamEvidence, ...] = field(repr=True)

    def __init__(self, *streams: ReadingTextStreamEvidence) -> None:
        values = tuple(streams)
        if not values:
            raise ReadingEvidenceError(
                "text stream inventory must not be empty"
            )
        if any(
            type(value) is not ReadingTextStreamEvidence for value in values
        ):
            raise TypeError("text stream inventory contains an invalid value")
        page = values[0].page_location
        if any(value.page_location != page for value in values):
            raise ReadingEvidenceError(
                "text streams must describe one exact page"
            )
        kinds = tuple(value.kind for value in values)
        if kinds != tuple(sorted(kinds, key=lambda value: value.value)):
            raise ReadingEvidenceError("text streams must be sorted by kind")
        if len(kinds) != len(set(kinds)):
            raise ReadingEvidenceError("text stream kinds must be unique")
        if ReadingTextStreamKind.NATIVE not in kinds:
            raise ReadingEvidenceError(
                "text stream inventory requires native evidence"
            )
        if len(values) > READING_EVIDENCE_LIMITS.maximum_streams_per_page:
            raise ReadingEvidenceLimitError(
                "text stream count exceeds its per-page limit"
            )
        object.__setattr__(self, "page_location", page)
        object.__setattr__(self, "_streams", values)

    def __iter__(self) -> Iterator[ReadingTextStreamEvidence]:
        return iter(self._streams)

    def __len__(self) -> int:
        return len(self._streams)

    def require(
        self, stream_id: ReadingEvidenceIdentity
    ) -> ReadingTextStreamEvidence:
        """Return one exact stream by typed identity."""
        if type(stream_id) is not ReadingEvidenceIdentity or (
            stream_id.kind is not ReadingEvidenceIdentityKind.TEXT_STREAM
        ):
            raise TypeError("stream_id must be a text-stream identity")
        for stream in self._streams:
            if stream.stream_id == stream_id:
                return stream
        raise ReadingEvidenceError("selected text stream is absent")

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical stream identity material."""
        return [stream.stream_id.value for stream in self._streams]
