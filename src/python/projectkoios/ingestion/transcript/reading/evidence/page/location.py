"""Canonical physical and printed reading page locations."""

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


@dataclass(frozen=True, slots=True)
class ReadingPageLocation:
    """Bind zero-based physical order to optional printed citation text."""

    physical_page_index: int
    printed_page_label: str | None = None
    location_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        index = READING_EVIDENCE_LIMITS.require_nonnegative_int(
            self.physical_page_index, "physical_page_index"
        )
        if index >= READING_EVIDENCE_LIMITS.maximum_pages:
            raise ReadingEvidenceError(
                "physical_page_index exceeds the page limit"
            )
        label = READING_EVIDENCE_LIMITS.require_optional_text(
            self.printed_page_label, "printed_page_label"
        )
        object.__setattr__(
            self,
            "location_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.PAGE_LOCATION,
                prefix="reading-page-location",
                material={
                    "physical_page_index": index,
                    "printed_page_label": label,
                },
            ),
        )

    @property
    def physical_page_number(self) -> int:
        """Return the positive physical page number."""
        return self.physical_page_index + 1
