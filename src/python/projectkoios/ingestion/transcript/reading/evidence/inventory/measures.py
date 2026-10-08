"""Complete bounded measures for canonical reading evidence inventories."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.sha256.hash import SHA256Hash
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
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceInventoryMeasures:
    """Carry complete current-contract counts and semantic digests."""

    page_count: int
    stream_count: int
    selection_count: int
    block_count: int
    paragraph_count: int
    heading_count: int
    figure_count: int
    table_count: int
    equation_count: int
    caption_count: int
    gate_count: int
    association_count: int
    artifact_count: int
    character_count: int
    utf8_byte_count: int
    limitation_count: int
    pages_sha256: SHA256Hash
    blocks_sha256: SHA256Hash
    producers_sha256: SHA256Hash
    artifacts_sha256: SHA256Hash
    limitations_sha256: SHA256Hash
    lineage_id: ReadingEvidenceIdentity
    measures_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        count_names = (
            "page_count",
            "stream_count",
            "selection_count",
            "block_count",
            "paragraph_count",
            "heading_count",
            "figure_count",
            "table_count",
            "equation_count",
            "caption_count",
            "gate_count",
            "association_count",
            "artifact_count",
            "character_count",
            "utf8_byte_count",
            "limitation_count",
        )
        for name in count_names:
            READING_EVIDENCE_LIMITS.require_nonnegative_int(
                getattr(self, name), name
            )
        maximums = {
            "page_count": READING_EVIDENCE_LIMITS.maximum_pages,
            "stream_count": (
                READING_EVIDENCE_LIMITS.maximum_pages
                * READING_EVIDENCE_LIMITS.maximum_streams_per_page
            ),
            "selection_count": READING_EVIDENCE_LIMITS.maximum_pages,
            "block_count": READING_EVIDENCE_LIMITS.maximum_blocks,
            "paragraph_count": READING_EVIDENCE_LIMITS.maximum_blocks,
            "heading_count": READING_EVIDENCE_LIMITS.maximum_blocks,
            "figure_count": READING_EVIDENCE_LIMITS.maximum_records,
            "table_count": READING_EVIDENCE_LIMITS.maximum_records,
            "equation_count": READING_EVIDENCE_LIMITS.maximum_records,
            "caption_count": READING_EVIDENCE_LIMITS.maximum_records,
            "gate_count": READING_EVIDENCE_LIMITS.maximum_records,
            "association_count": READING_EVIDENCE_LIMITS.maximum_records,
            "artifact_count": READING_EVIDENCE_LIMITS.maximum_references,
            "character_count": (
                READING_EVIDENCE_LIMITS.maximum_aggregate_characters
            ),
            "utf8_byte_count": (
                READING_EVIDENCE_LIMITS.maximum_document_text_bytes
                + READING_EVIDENCE_LIMITS.maximum_document_clean_text_bytes
            ),
            "limitation_count": (READING_EVIDENCE_LIMITS.maximum_limitations),
        }
        for name, maximum in maximums.items():
            if getattr(self, name) > maximum:
                raise ReadingEvidenceLimitError(f"{name} exceeds its limit")
        if (
            self.selection_count != self.page_count
            or not self.page_count
            <= self.stream_count
            <= (
                self.page_count
                * READING_EVIDENCE_LIMITS.maximum_streams_per_page
            )
            or self.paragraph_count + self.heading_count > self.block_count
            or self.caption_count > self.figure_count
            or self.gate_count != self.equation_count
        ):
            raise ReadingEvidenceError(
                "reading evidence inventory measures are inconsistent"
            )
        digests = (
            self.pages_sha256,
            self.blocks_sha256,
            self.producers_sha256,
            self.artifacts_sha256,
            self.limitations_sha256,
        )
        for name, value in zip(
            (
                "pages_sha256",
                "blocks_sha256",
                "producers_sha256",
                "artifacts_sha256",
                "limitations_sha256",
            ),
            digests,
            strict=True,
        ):
            READING_EVIDENCE_LIMITS.require_sha256(value, name)
        if (
            type(self.lineage_id) is not ReadingEvidenceIdentity
            or self.lineage_id.kind is not ReadingEvidenceIdentityKind.LINEAGE
        ):
            raise TypeError("lineage_id has the wrong identity role")
        object.__setattr__(
            self,
            "measures_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.EVIDENCE_INVENTORY,
                prefix="reading-evidence-measures",
                material={name: getattr(self, name) for name in count_names}
                | {
                    "pages_sha256": self.pages_sha256,
                    "blocks_sha256": self.blocks_sha256,
                    "producers_sha256": self.producers_sha256,
                    "artifacts_sha256": self.artifacts_sha256,
                    "limitations_sha256": self.limitations_sha256,
                    "lineage_id": self.lineage_id.value,
                },
            ),
        )
