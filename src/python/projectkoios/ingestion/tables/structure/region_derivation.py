"""Immutable derivation of rows and cells for one candidate region."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.tables.contracts import (
    TableBoundaryKind,
    TableCandidate,
    TableRegionEvidence,
    TableRuleOrientation,
    TableRuleSegment,
)
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.bounds import _HEADER
from projectkoios.ingestion.tables.structure.cell import TableCell
from projectkoios.ingestion.tables.structure.cell_derivation import (
    TableCellDerivation,
)
from projectkoios.ingestion.tables.structure.cell_role import TableCellRole
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)
from projectkoios.ingestion.tables.structure.row import TableRow
from projectkoios.ingestion.tables.structure.source_record import (
    TableSourceRecord,
)
from projectkoios.ingestion.tables.structure.warning_specification import (
    TableStructureWarningSpecification,
)


@dataclass(frozen=True)
class TableRegionDerivation(
    AbstractTableStructureDataObject, AbstractDerivation
):
    """Represent deterministic rows, cells, and warnings for one region."""

    CONTRACT_NAME: ClassVar[str] = "table-region-derivation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    rows: tuple[TableRow, ...]
    cells: tuple[TableCell, ...]
    warning_specifications: tuple[TableStructureWarningSpecification, ...]
    first_header_texts: tuple[str, ...] | None
    next_reading_order: int

    def __post_init__(self) -> None:
        for name, values, expected_type in (
            ("rows", self.rows, TableRow),
            ("cells", self.cells, TableCell),
            (
                "warning specifications",
                self.warning_specifications,
                TableStructureWarningSpecification,
            ),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(item, expected_type) for item in values
            ):
                raise TypeError(f"region derivation requires immutable {name}")
        if self.first_header_texts is not None and (
            not isinstance(self.first_header_texts, tuple)
            or any(
                not isinstance(item, str) for item in self.first_header_texts
            )
        ):
            raise TypeError("first header texts must be an immutable tuple")
        self._validate_nonnegative_integer(
            "next reading order", self.next_reading_order
        )

    @classmethod
    def create(
        cls,
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        region: TableRegionEvidence,
        column_boundaries: tuple[float, ...],
        column_count: int,
        first_header_texts: tuple[str, ...] | None,
        reading_order: int,
        processor_name: str,
        processor_version: str,
    ) -> TableRegionDerivation:
        detection = structure_input.detection_result
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
        records = tuple(
            TableSourceRecord.from_block(blocks[block_id], order)
            for order, block_id in enumerate(region.block_ids)
        )
        row_groups = TableSourceRecord.cluster_rows(
            records,
            detection.detection_input.configuration.row_alignment_tolerance_points,
        )
        if len(row_groups) != region.row_band_count:
            raise ValueError("candidate row evidence cannot be reconstructed")
        header_flags = tuple(
            any(_HEADER.search(record.block.text or "") for record in group)
            for group in row_groups
        )
        header_row_index = next(
            (index for index, value in enumerate(header_flags) if value),
            None,
        )
        header_texts = (
            None
            if header_row_index is None
            else tuple(
                record.block.text or ""
                for record in row_groups[header_row_index]
            )
        )
        region_repeats_header = cls._repeats_header(
            first_header_texts, header_texts
        )
        updated_first_header_texts = (
            header_texts
            if first_header_texts is None and header_texts is not None
            else first_header_texts
        )
        row_boundaries = cls._row_boundaries(region, row_groups, rules)
        rows: list[TableRow] = []
        cells: list[TableCell] = []
        warnings: list[TableStructureWarningSpecification] = []
        next_order = reading_order
        for page_row_index, group in enumerate(row_groups):
            row = cls._derive_row(
                structure_input=structure_input,
                candidate=candidate,
                region=region,
                page_row_index=page_row_index,
                reading_order=next_order,
                group=group,
                row_boundaries=row_boundaries,
                repeated_header=(
                    region_repeats_header and header_flags[page_row_index]
                ),
                processor_name=processor_name,
                processor_version=processor_version,
            )
            rows.append(row)
            next_order += 1
            role = cls._cell_role(
                row_is_header=header_flags[page_row_index],
                header_row_index=header_row_index,
                page_row_index=page_row_index,
            )
            derived_cells, derived_warnings = cls._derive_cells(
                structure_input=structure_input,
                candidate=candidate,
                region=region,
                row=row,
                page_row_index=page_row_index,
                group=group,
                column_boundaries=column_boundaries,
                column_count=column_count,
                role=role,
                processor_name=processor_name,
                processor_version=processor_version,
            )
            cells.extend(derived_cells)
            warnings.extend(derived_warnings)
        warnings.extend(
            cls._region_warning_specifications(
                candidate=candidate,
                region=region,
                row_groups=row_groups,
                header_row_index=header_row_index,
            )
        )
        return cls(
            rows=tuple(rows),
            cells=tuple(cells),
            warning_specifications=tuple(warnings),
            first_header_texts=updated_first_header_texts,
            next_reading_order=next_order,
        )

    @staticmethod
    def _derive_row(
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        region: TableRegionEvidence,
        page_row_index: int,
        reading_order: int,
        group: tuple[TableSourceRecord, ...],
        row_boundaries: tuple[float, ...],
        repeated_header: bool,
        processor_name: str,
        processor_version: str,
    ) -> TableRow:
        return TableRow.create(
            structure_input_id=structure_input.input_id,
            candidate_id=candidate.candidate_id,
            region_id=region.region_evidence_id,
            page_index=region.page_index,
            page_row_index=page_row_index,
            reading_order=reading_order,
            source_bounding_box=(
                region.source_bounding_box[0],
                row_boundaries[page_row_index],
                region.source_bounding_box[2],
                row_boundaries[page_row_index + 1],
            ),
            source_block_ids=tuple(record.block.block_id for record in group),
            source_spans=tuple(
                span for record in group for span in record.block.source_spans
            ),
            repeated_header=repeated_header,
            confidence=region.confidence,
            evidence=(
                ("row_method", "rules_or_text_midpoints"),
                (
                    "explicit_header",
                    str(
                        any(
                            _HEADER.search(record.block.text or "")
                            for record in group
                        )
                    ).lower(),
                ),
            ),
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=(
                structure_input.configuration.configuration_digest
            ),
        )

    @classmethod
    def _derive_cells(
        cls,
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        region: TableRegionEvidence,
        row: TableRow,
        page_row_index: int,
        group: tuple[TableSourceRecord, ...],
        column_boundaries: tuple[float, ...],
        column_count: int,
        role: TableCellRole,
        processor_name: str,
        processor_version: str,
    ) -> tuple[
        tuple[TableCell, ...],
        tuple[TableStructureWarningSpecification, ...],
    ]:
        merged_records = tuple(
            record
            for record in group
            if record.block.block_id in region.merged_cell_signal_block_ids
        )
        if len(group) == 1 and len(merged_records) == 1:
            cell = cls._cell(
                structure_input=structure_input,
                candidate=candidate,
                region=region,
                row=row,
                page_row_index=page_row_index,
                column_index=0,
                column_span=column_count,
                role=role,
                records=merged_records,
                status=TableStructureEvidenceStatus.AMBIGUOUS,
                processor_name=processor_name,
                processor_version=processor_version,
            )
            return (cell,), (
                TableStructureWarningSpecification(
                    code="table_structure.merged_span_ambiguous",
                    message=(
                        "A candidate merged row is represented as a "
                        "full-column span proposal"
                    ),
                    object_ids=(cell.cell_id,),
                    source_spans=cell.source_spans,
                ),
            )
        warnings: list[TableStructureWarningSpecification] = []
        if merged_records:
            warnings.append(
                TableStructureWarningSpecification(
                    code="table_structure.merged_span_unresolved",
                    message=(
                        "Merged-cell geometry overlaps other row blocks; "
                        "all blocks remain ambiguous column proposals"
                    ),
                    object_ids=tuple(
                        record.block.block_id for record in merged_records
                    ),
                    source_spans=tuple(
                        span
                        for record in merged_records
                        for span in record.block.source_spans
                    ),
                )
            )
        slots: dict[int, list[TableSourceRecord]] = {
            index: [] for index in range(column_count)
        }
        for record in group:
            slots[
                TableSourceRecord.column_for(record.center_x, column_boundaries)
            ].append(record)
        cells: list[TableCell] = []
        for column_index in range(column_count):
            assigned = tuple(slots[column_index])
            status = cls._cell_status(assigned, merged_records)
            cell = cls._cell(
                structure_input=structure_input,
                candidate=candidate,
                region=region,
                row=row,
                page_row_index=page_row_index,
                column_index=column_index,
                column_span=1,
                role=role,
                records=assigned,
                status=status,
                processor_name=processor_name,
                processor_version=processor_version,
            )
            cells.append(cell)
            warning = cls._cell_warning(cell, assigned)
            if warning is not None:
                warnings.append(warning)
        return tuple(cells), tuple(warnings)

    @staticmethod
    def _cell(
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        region: TableRegionEvidence,
        row: TableRow,
        page_row_index: int,
        column_index: int,
        column_span: int,
        role: TableCellRole,
        records: tuple[TableSourceRecord, ...],
        status: TableStructureEvidenceStatus,
        processor_name: str,
        processor_version: str,
    ) -> TableCell:
        return TableCellDerivation.create(
            structure_input=structure_input,
            candidate=candidate,
            region=region,
            row=row,
            page_row_index=page_row_index,
            column_index=column_index,
            row_span=1,
            column_span=column_span,
            role=role,
            records=records,
            status=status,
            processor_name=processor_name,
            processor_version=processor_version,
        ).cell

    @staticmethod
    def _cell_status(
        assigned: tuple[TableSourceRecord, ...],
        merged_records: tuple[TableSourceRecord, ...],
    ) -> TableStructureEvidenceStatus:
        if not assigned or len(assigned) > 1:
            return TableStructureEvidenceStatus.AMBIGUOUS
        if any(record in merged_records for record in assigned):
            return TableStructureEvidenceStatus.AMBIGUOUS
        return TableStructureEvidenceStatus.PROPOSED

    @staticmethod
    def _cell_warning(
        cell: TableCell,
        assigned: tuple[TableSourceRecord, ...],
    ) -> TableStructureWarningSpecification | None:
        if not assigned:
            return TableStructureWarningSpecification(
                code="table_structure.empty_cell",
                message=(
                    "A proposed grid position has no native text block and "
                    "retains rendered-region evidence"
                ),
                object_ids=(cell.cell_id,),
                source_spans=(),
            )
        if len(assigned) > 1:
            return TableStructureWarningSpecification(
                code="table_structure.multiple_blocks_in_cell",
                message="Multiple native blocks map to one proposed cell",
                object_ids=(cell.cell_id,),
                source_spans=cell.source_spans,
            )
        return None

    @staticmethod
    def _cell_role(
        *,
        row_is_header: bool,
        header_row_index: int | None,
        page_row_index: int,
    ) -> TableCellRole:
        if row_is_header:
            return TableCellRole.HEADER
        if header_row_index is None or page_row_index < header_row_index:
            return TableCellRole.UNKNOWN
        return TableCellRole.BODY

    @staticmethod
    def _row_boundaries(
        region: TableRegionEvidence,
        rows: tuple[tuple[TableSourceRecord, ...], ...],
        rules: dict[str, TableRuleSegment],
    ) -> tuple[float, ...]:
        horizontal = sorted(
            {
                segment.start[1]
                for segment_id in region.rule_segment_ids
                if (segment := rules[segment_id]).orientation
                is TableRuleOrientation.HORIZONTAL
            }
        )
        if len(horizontal) == len(rows) + 1:
            return tuple(horizontal)
        centers = tuple(
            sum(record.center_y for record in row) / len(row) for row in rows
        )
        boundaries = [region.source_bounding_box[1]]
        boundaries.extend(
            (top + bottom) / 2.0
            for top, bottom in zip(centers, centers[1:], strict=False)
        )
        boundaries.append(region.source_bounding_box[3])
        return tuple(boundaries)

    @staticmethod
    def _repeats_header(
        first_header_texts: tuple[str, ...] | None,
        header_texts: tuple[str, ...] | None,
    ) -> bool:
        return (
            first_header_texts is not None
            and header_texts is not None
            and tuple(
                TableSourceRecord.normalized_text(text) for text in header_texts
            )
            == tuple(
                TableSourceRecord.normalized_text(text)
                for text in first_header_texts
            )
        )

    @staticmethod
    def _region_warning_specifications(
        *,
        candidate: TableCandidate,
        region: TableRegionEvidence,
        row_groups: tuple[tuple[TableSourceRecord, ...], ...],
        header_row_index: int | None,
    ) -> tuple[TableStructureWarningSpecification, ...]:
        warnings: list[TableStructureWarningSpecification] = []
        if header_row_index is None:
            warnings.append(
                TableStructureWarningSpecification(
                    code="table_structure.header_unresolved",
                    message="No explicit header evidence was observed",
                    object_ids=(),
                    source_spans=tuple(
                        span
                        for record in row_groups[0]
                        for span in record.block.source_spans
                    ),
                    evidence=(("page_index", str(region.page_index)),),
                )
            )
        if candidate.boundary_kind is TableBoundaryKind.UNRULED:
            warnings.append(
                TableStructureWarningSpecification(
                    code="table_structure.unruled_geometry",
                    message=(
                        "Column and row boundaries rely on native-text geometry"
                    ),
                    object_ids=(),
                    source_spans=region.source_spans,
                )
            )
        elif candidate.boundary_kind is TableBoundaryKind.MIXED:
            warnings.append(
                TableStructureWarningSpecification(
                    code="table_structure.mixed_boundary_geometry",
                    message=(
                        "Table boundaries combine incomplete rules and "
                        "native-text geometry"
                    ),
                    object_ids=(),
                    source_spans=region.source_spans,
                )
            )
        return tuple(warnings)
