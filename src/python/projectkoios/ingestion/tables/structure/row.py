"""TableRow table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import BoundingBox, Metadata, SourceSpan
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)


@dataclass(frozen=True)
class TableRow(AbstractTableStructureDataObject):
    row_id: str
    structure_input_id: str
    candidate_id: str
    region_id: str
    page_index: int
    page_row_index: int
    reading_order: int
    source_bounding_box: BoundingBox
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    repeated_header: bool
    confidence: float
    evidence: Metadata
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input_id: str,
        candidate_id: str,
        region_id: str,
        page_index: int,
        page_row_index: int,
        reading_order: int,
        source_bounding_box: BoundingBox,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        repeated_header: bool,
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableRow:
        box, normalized_confidence = cls._validated_parts(
            structure_input_id,
            candidate_id,
            region_id,
            page_index,
            page_row_index,
            reading_order,
            source_bounding_box,
            source_block_ids,
            source_spans,
            repeated_header,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        row_id = cls._derived_id(
            structure_input_id,
            candidate_id,
            region_id,
            page_index,
            page_row_index,
            reading_order,
            box,
            source_block_ids,
            source_spans,
            repeated_header,
            normalized_confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            row_id=row_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            region_id=region_id,
            page_index=page_index,
            page_row_index=page_row_index,
            reading_order=reading_order,
            source_bounding_box=box,
            source_block_ids=source_block_ids,
            source_spans=source_spans,
            repeated_header=repeated_header,
            confidence=normalized_confidence,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table row version")
        box, confidence = self._validated_parts(
            self.structure_input_id,
            self.candidate_id,
            self.region_id,
            self.page_index,
            self.page_row_index,
            self.reading_order,
            self.source_bounding_box,
            self.source_block_ids,
            self.source_spans,
            self.repeated_header,
            self.confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "source_bounding_box", box)
        object.__setattr__(self, "confidence", confidence)
        if self.row_id != self._derived_id(
            self.structure_input_id,
            self.candidate_id,
            self.region_id,
            self.page_index,
            self.page_row_index,
            self.reading_order,
            box,
            self.source_block_ids,
            self.source_spans,
            self.repeated_header,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table row ID is inconsistent")

    @classmethod
    def _validated_parts(
        cls,
        structure_input_id: str,
        candidate_id: str,
        region_id: str,
        page_index: int,
        page_row_index: int,
        reading_order: int,
        source_bounding_box: BoundingBox,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        repeated_header: bool,
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> tuple[BoundingBox, float]:
        cls._validate_identity_fields(
            structure_input_id,
            candidate_id,
            region_id,
            processor_name,
            processor_version,
            configuration_digest,
        )
        cls._validate_nonnegative_integer("row page index", page_index)
        cls._validate_nonnegative_integer("page row index", page_row_index)
        cls._validate_nonnegative_integer("row reading order", reading_order)
        box = cls._validate_box(source_bounding_box)
        cls._validate_unique_strings(
            "row source block IDs", source_block_ids, required=True
        )
        cls._validate_spans(source_spans)
        if not isinstance(repeated_header, bool):
            raise TypeError("repeated_header must be a boolean")
        cls._validate_metadata(evidence)
        return box, cls._validate_unit_float("row confidence", confidence)

    @staticmethod
    def _derived_id(
        structure_input_id: str,
        candidate_id: str,
        region_id: str,
        page_index: int,
        page_row_index: int,
        reading_order: int,
        source_bounding_box: BoundingBox,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        repeated_header: bool,
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> str:
        return stable_id(
            "table-row",
            structure_input_id,
            candidate_id,
            region_id,
            page_index,
            page_row_index,
            reading_order,
            source_bounding_box,
            source_block_ids,
            tuple(span.identity_parts() for span in source_spans),
            repeated_header,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
