"""Immutable validation evidence for derived table cells."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.models import ExtractedBlock
from projectkoios.ingestion.tables.contracts import TableRegionEvidence
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.cell import TableCell
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.model import TableStructure
from projectkoios.ingestion.tables.structure.row import TableRow


@dataclass(frozen=True)
class TableCellValidation(AbstractTableStructureDataObject, AbstractValidation):
    """Record successful cross-object validation of derived cells."""

    CONTRACT_NAME: ClassVar[str] = "table-cell-validation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    structure_id: str
    validated_cell_count: int

    def __post_init__(self) -> None:
        self._validate_identity_fields(self.structure_id)
        self._validate_nonnegative_integer(
            "validated cell count", self.validated_cell_count
        )

    @classmethod
    def create(
        cls,
        *,
        structure: TableStructure,
        regions: tuple[TableRegionEvidence, ...],
        blocks: tuple[ExtractedBlock, ...],
    ) -> TableCellValidation:
        block_by_id = {block.block_id: block for block in blocks}
        region_by_id = {region.region_evidence_id: region for region in regions}
        row_by_id = {row.row_id: row for row in structure.rows}
        occupied: set[tuple[int, int]] = set()
        assigned_by_region: dict[str, list[str]] = {
            region_id: [] for region_id in region_by_id
        }
        for cell in structure.cells:
            cell_row = row_by_id.get(cell.row_id)
            if cell_row is None:
                raise ValueError("cell references an unknown row")
            cls._validate_derivation(structure, cell, cell_row)
            cls._record_positions(structure, cell, cell_row, occupied)
            region = region_by_id[cell_row.region_id]
            if cell.rendered_region_ids != (region.rendered_region.region_id,):
                raise ValueError("cell rendered evidence is inconsistent")
            source_blocks = tuple(
                block_by_id[item] for item in cell.source_block_ids
            )
            if cell.source_texts != tuple(
                block.text or "" for block in source_blocks
            ):
                raise ValueError("cell source text is inconsistent")
            if cell.source_spans != tuple(
                span for block in source_blocks for span in block.source_spans
            ):
                raise ValueError("cell source spans are inconsistent")
            assigned_by_region[cell_row.region_id].extend(cell.source_block_ids)
            expected_text = (
                None if not cell.source_texts else "\n".join(cell.source_texts)
            )
            if cell.proposed_text != expected_text:
                raise ValueError("cell proposed text is inconsistent")
            if not cell.source_block_ids and not cell.rendered_region_ids:
                raise ValueError("cell lacks source block or rendered evidence")
        cls._validate_complete_grid(structure, occupied)
        cls._validate_region_assignments(region_by_id, assigned_by_region)
        cls._validate_row_evidence(structure, row_by_id)
        return cls(
            structure_id=structure.structure_id,
            validated_cell_count=len(structure.cells),
        )

    @staticmethod
    def _validate_derivation(
        structure: TableStructure,
        cell: TableCell,
        cell_row: TableRow,
    ) -> None:
        if (
            cell.row_index != cell_row.reading_order
            or cell.page_index != cell_row.page_index
        ):
            raise ValueError("cell row evidence is inconsistent")
        if (
            cell.structure_input_id != structure.structure_input_id
            or cell.candidate_id != structure.candidate_id
            or cell.processor_name != structure.processor_name
            or cell.processor_version != structure.processor_version
            or cell.configuration_digest != structure.configuration_digest
        ):
            raise ValueError("cell derivation evidence is inconsistent")
        if cell.column_index + cell.column_span > len(structure.columns):
            raise ValueError("cell column span exceeds table columns")

    @staticmethod
    def _record_positions(
        structure: TableStructure,
        cell: TableCell,
        cell_row: TableRow,
        occupied: set[tuple[int, int]],
    ) -> None:
        for row_offset in range(cell.row_span):
            covered_row_index = cell.row_index + row_offset
            if covered_row_index >= len(structure.rows):
                raise ValueError("cell row span exceeds table rows")
            covered_row = structure.rows[covered_row_index]
            if (
                covered_row.page_index != cell_row.page_index
                or covered_row.region_id != cell_row.region_id
            ):
                raise ValueError("cell row span crosses a page region")
            for column_offset in range(cell.column_span):
                position = (
                    covered_row_index,
                    cell.column_index + column_offset,
                )
                if position in occupied:
                    raise ValueError("table cells overlap")
                occupied.add(position)

    @staticmethod
    def _validate_complete_grid(
        structure: TableStructure,
        occupied: set[tuple[int, int]],
    ) -> None:
        expected_positions = {
            (row.reading_order, column.column_index)
            for row in structure.rows
            for column in structure.columns
        }
        if occupied != expected_positions:
            raise ValueError("table cell grid is incomplete")

    @staticmethod
    def _validate_region_assignments(
        region_by_id: dict[str, TableRegionEvidence],
        assigned_by_region: dict[str, list[str]],
    ) -> None:
        for region_id, assigned in assigned_by_region.items():
            expected = region_by_id[region_id].block_ids
            if len(assigned) != len(expected) or set(assigned) != set(expected):
                raise ValueError(
                    "region source blocks are not assigned exactly once"
                )

    @staticmethod
    def _validate_row_evidence(
        structure: TableStructure,
        row_by_id: dict[str, TableRow],
    ) -> None:
        cells_by_row: dict[str, list[TableCell]] = {
            row_id: [] for row_id in row_by_id
        }
        for cell in structure.cells:
            cells_by_row[cell.row_id].append(cell)
        for row in structure.rows:
            row_cells = cells_by_row[row.row_id]
            expected_block_ids = tuple(
                block_id
                for cell in row_cells
                for block_id in cell.source_block_ids
            )
            expected_spans = tuple(
                span for cell in row_cells for span in cell.source_spans
            )
            if (
                len(row.source_block_ids) != len(expected_block_ids)
                or set(row.source_block_ids) != set(expected_block_ids)
                or Counter(row.source_spans) != Counter(expected_spans)
            ):
                raise ValueError(
                    "row source evidence is inconsistent with its cells"
                )
