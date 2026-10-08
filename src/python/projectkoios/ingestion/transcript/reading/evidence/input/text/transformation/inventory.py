"""Ordered exact clean-text transformation inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.definition import (  # noqa: E501
    ReadingTextTransformation,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingTextTransformationInventory:
    """Own an ordered, unique, bounded transformation collection."""

    _transformations: tuple[ReadingTextTransformation, ...] = field(repr=True)

    def __init__(self, *transformations: ReadingTextTransformation) -> None:
        values = tuple(transformations)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_transformations:
            raise ReadingEvidenceLimitError(
                "text transformation count exceeds its limit"
            )
        if any(
            type(value) is not ReadingTextTransformation for value in values
        ):
            raise TypeError(
                "transformation inventory contains an invalid value"
            )
        order = tuple(
            (value.source_start_offset, value.source_end_offset)
            for value in values
        )
        if order != tuple(sorted(order)):
            raise ReadingEvidenceError(
                "text transformations must be source ordered"
            )
        if any(
            current.source_start_offset < previous.source_end_offset
            for previous, current in zip(values, values[1:], strict=False)
        ):
            raise ReadingEvidenceError("text transformations must not overlap")
        identities = tuple(value.transformation_id.value for value in values)
        if len(identities) != len(set(identities)):
            raise ReadingEvidenceError("text transformations must be unique")
        object.__setattr__(self, "_transformations", values)

    def __bool__(self) -> bool:
        return bool(self._transformations)

    def __iter__(self) -> Iterator[ReadingTextTransformation]:
        return iter(self._transformations)

    def __len__(self) -> int:
        return len(self._transformations)

    def apply(self, source_text: str) -> str:
        """Apply the exact non-overlapping transformations to source text."""
        source = READING_EVIDENCE_LIMITS.require_string(
            source_text,
            "source_text",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        pieces: list[str] = []
        cursor = 0
        for transformation in self._transformations:
            if transformation.source_end_offset > len(source):
                raise ReadingEvidenceError(
                    "text transformation exceeds source text"
                )
            pieces.extend(
                (
                    source[cursor : transformation.source_start_offset],
                    transformation.replacement_text,
                )
            )
            cursor = transformation.source_end_offset
        pieces.append(source[cursor:])
        return "".join(pieces)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical transformation identity material."""
        return [
            value.transformation_id.value for value in self._transformations
        ]
