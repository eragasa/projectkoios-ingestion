"""Immutable derivation of one table cell from ordered source records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.models import Metadata
from projectkoios.ingestion.tables.contracts import (
    TableCandidate,
    TableRegionEvidence,
)
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.cell import TableCell
from projectkoios.ingestion.tables.structure.cell_role import TableCellRole
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)
from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)
from projectkoios.ingestion.tables.structure.row import TableRow
from projectkoios.ingestion.tables.structure.source_record import (
    TableSourceRecord,
)


@dataclass(frozen=True)
class TableCellDerivation(AbstractTableStructureDataObject):
    """Represent the deterministic output of one cell-derivation step."""

    CONTRACT_NAME: ClassVar[str] = "table-cell-derivation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    cell: TableCell

    def __post_init__(self) -> None:
        if not isinstance(self.cell, TableCell):
            raise TypeError("cell derivation requires a TableCell")

    @classmethod
    def create(
        cls,
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        region: TableRegionEvidence,
        row: TableRow,
        page_row_index: int,
        column_index: int,
        row_span: int,
        column_span: int,
        role: TableCellRole,
        records: tuple[TableSourceRecord, ...],
        status: TableStructureEvidenceStatus,
        processor_name: str,
        processor_version: str,
    ) -> TableCellDerivation:
        configuration = structure_input.configuration
        if len(records) > configuration.max_blocks_per_cell:
            raise TableStructureLimitError(
                "cell blocks exceed max_blocks_per_cell"
            )
        texts = tuple(record.block.text or "" for record in records)
        proposed_text = None if not texts else "\n".join(texts)
        join_method = (
            None
            if not texts
            else (
                "single_source_block_exact"
                if len(texts) == 1
                else "source_blocks_newline_in_reading_order"
            )
        )
        source_spans = tuple(
            span for record in records for span in record.block.source_spans
        )
        confidence = (
            0.35
            if not records
            else min(record.block.confidence for record in records)
        )
        evidence: Metadata = (
            ("source_block_count", str(len(records))),
            ("render_scope", "candidate_region"),
        )
        return cls(
            cell=TableCell.create(
                structure_input_id=structure_input.input_id,
                candidate_id=candidate.candidate_id,
                row_id=row.row_id,
                page_index=region.page_index,
                row_index=row.reading_order,
                column_index=column_index,
                row_span=row_span,
                column_span=column_span,
                role=role,
                evidence_status=status,
                proposed_text=proposed_text,
                text_join_method=join_method,
                source_texts=texts,
                source_block_ids=tuple(
                    record.block.block_id for record in records
                ),
                source_spans=source_spans,
                rendered_region_ids=(region.rendered_region.region_id,),
                confidence=confidence,
                evidence=evidence,
                warning_ids=(),
                processor_name=processor_name,
                processor_version=processor_version,
                configuration_digest=configuration.configuration_digest,
            )
        )
