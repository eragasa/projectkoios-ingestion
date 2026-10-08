"""Exact page-bound reading source spans."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.span.geometry import (
    ReadingBoundingBox,
)


@dataclass(frozen=True, slots=True)
class ReadingSourceSpanEvidence:
    """Bind exact source identity, page, geometry, and text offsets."""

    source_id: ReadingEvidenceIdentity
    page_location: ReadingPageLocation
    source_object_id: ReadingEvidenceIdentity | None = None
    bounding_box: ReadingBoundingBox | None = None
    geometry_warning_id: ReadingEvidenceIdentity | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    span_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.source_id) is not ReadingEvidenceIdentity
            or self.source_id.kind is not ReadingEvidenceIdentityKind.SOURCE
        ):
            raise TypeError("source_id must be a source identity")
        if type(self.page_location) is not ReadingPageLocation:
            raise TypeError("page_location must be ReadingPageLocation")
        if self.source_object_id is not None and (
            type(self.source_object_id) is not ReadingEvidenceIdentity
            or self.source_object_id.kind
            is not ReadingEvidenceIdentityKind.SOURCE_OBJECT
        ):
            raise TypeError("source_object_id must be a source-object identity")
        if self.bounding_box is not None and (
            type(self.bounding_box) is not ReadingBoundingBox
        ):
            raise TypeError("bounding_box must be ReadingBoundingBox")
        if self.geometry_warning_id is not None and (
            type(self.geometry_warning_id) is not ReadingEvidenceIdentity
            or self.geometry_warning_id.kind
            is not ReadingEvidenceIdentityKind.WARNING
        ):
            raise TypeError("geometry_warning_id must be a warning identity")
        if (
            self.bounding_box is not None
            and self.geometry_warning_id is not None
        ):
            raise ReadingEvidenceError(
                "valid geometry cannot carry a geometry warning"
            )
        if (self.start_offset is None) != (self.end_offset is None):
            raise ReadingEvidenceError(
                "source offsets must be supplied together"
            )
        if self.start_offset is not None and self.end_offset is not None:
            start = READING_EVIDENCE_LIMITS.require_nonnegative_int(
                self.start_offset, "start_offset"
            )
            end = READING_EVIDENCE_LIMITS.require_nonnegative_int(
                self.end_offset, "end_offset"
            )
            if end < start:
                raise ReadingEvidenceError("source offsets must be ordered")
        object.__setattr__(
            self,
            "span_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.SOURCE_SPAN,
                prefix="reading-source-span",
                material={
                    "source_id": self.source_id.value,
                    "page_location_id": self.page_location.location_id.value,
                    "source_object_id": (
                        None
                        if self.source_object_id is None
                        else self.source_object_id.value
                    ),
                    "bounding_box": (
                        None
                        if self.bounding_box is None
                        else self.bounding_box.identity_material()
                    ),
                    "geometry_warning_id": (
                        None
                        if self.geometry_warning_id is None
                        else self.geometry_warning_id.value
                    ),
                    "start_offset": self.start_offset,
                    "end_offset": self.end_offset,
                },
            ),
        )
