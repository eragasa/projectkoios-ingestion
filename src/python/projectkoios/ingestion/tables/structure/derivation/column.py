"""Immutable derivation of candidate-wide table columns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.models import ExtractedBlock
from projectkoios.ingestion.tables.contracts import (
    TableCandidate,
    TableRegionEvidence,
    TableRuleOrientation,
    TableRuleSegment,
)
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.column import TableColumn
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.limits.error import (
    TableStructureLimitError,
)
from projectkoios.ingestion.tables.structure.record.source import (
    TableSourceRecord,
)
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)


@dataclass(frozen=True)
class TableColumnDerivation(
    AbstractTableStructureDataObject, AbstractDerivation
):
    """Represent region boundaries and normalized candidate columns."""

    CONTRACT_NAME: ClassVar[str] = "table-column-derivation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    region_boundaries: tuple[tuple[float, ...], ...]
    columns: tuple[TableColumn, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.region_boundaries, tuple) or any(
            not isinstance(item, tuple) for item in self.region_boundaries
        ):
            raise TypeError(
                "column derivation requires immutable region boundaries"
            )
        if not isinstance(self.columns, tuple) or any(
            not isinstance(item, TableColumn) for item in self.columns
        ):
            raise TypeError("column derivation requires immutable columns")
        if len(self.region_boundaries) == 0 or len(self.columns) == 0:
            raise ValueError("column derivation cannot be empty")

    @classmethod
    def create(
        cls,
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        processor_name: str,
        processor_version: str,
    ) -> TableColumnDerivation:
        detection = structure_input.detection_result
        configuration = structure_input.configuration
        blocks = {
            block.block_id: block
            for page in detection.detection_input.document.pages
            for block in page.blocks
        }
        rules = {
            segment.segment_id: segment
            for page in detection.detection_input.page_rule_evidence
            for segment in page.segments
        }
        column_count = max(
            region.column_band_count for region in candidate.regions
        )
        if column_count > configuration.max_columns:
            raise TableStructureLimitError("columns exceed max_columns")
        region_boundaries = tuple(
            cls._region_boundaries(
                region=region,
                blocks=blocks,
                rules=rules,
                column_count=column_count,
                alignment_tolerance=(
                    detection.detection_input.configuration.column_alignment_tolerance_points
                ),
            )
            for region in candidate.regions
        )
        normalized_boundaries = tuple(
            sum(
                boundaries[index]
                / cls._page_width(structure_input, region.page_index)
                for region, boundaries in zip(
                    candidate.regions, region_boundaries, strict=True
                )
            )
            / len(candidate.regions)
            for index in range(column_count + 1)
        )
        columns = tuple(
            TableColumn.create(
                structure_input_id=structure_input.input_id,
                candidate_id=candidate.candidate_id,
                column_index=index,
                normalized_left=normalized_boundaries[index],
                normalized_right=normalized_boundaries[index + 1],
                source_region_ids=tuple(
                    region.region_evidence_id for region in candidate.regions
                ),
                confidence=min(
                    region.confidence for region in candidate.regions
                ),
                evidence=(("boundary_method", "rules_or_text_midpoints"),),
                processor_name=processor_name,
                processor_version=processor_version,
                configuration_digest=configuration.configuration_digest,
            )
            for index in range(column_count)
        )
        return cls(region_boundaries=region_boundaries, columns=columns)

    @staticmethod
    def _region_boundaries(
        *,
        region: TableRegionEvidence,
        blocks: dict[str, ExtractedBlock],
        rules: dict[str, TableRuleSegment],
        column_count: int,
        alignment_tolerance: float,
    ) -> tuple[float, ...]:
        vertical = sorted(
            {
                segment.start[0]
                for segment_id in region.rule_segment_ids
                if (segment := rules[segment_id]).orientation
                is TableRuleOrientation.VERTICAL
            }
        )
        if len(vertical) == column_count + 1:
            return tuple(vertical)
        records = tuple(
            TableSourceRecord.from_block(blocks[block_id], order)
            for order, block_id in enumerate(region.block_ids)
            if block_id not in region.merged_cell_signal_block_ids
        )
        anchors = TableSourceRecord.cluster_values(
            tuple(record.box[0] for record in records), alignment_tolerance
        )
        if len(anchors) != column_count:
            raise ValueError("candidate columns cannot be reconstructed")
        boundaries = [region.source_bounding_box[0]]
        boundaries.extend(
            (left + right) / 2.0
            for left, right in zip(anchors, anchors[1:], strict=False)
        )
        boundaries.append(region.source_bounding_box[2])
        return tuple(boundaries)

    @staticmethod
    def _page_width(
        structure_input: TableStructureRequest, page_index: int
    ) -> float:
        return next(
            page.width
            for page in (
                structure_input.detection_result.detection_input.document.pages
            )
            if page.page_index == page_index
        )
