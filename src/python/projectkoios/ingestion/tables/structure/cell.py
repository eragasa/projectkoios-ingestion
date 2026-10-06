"""TableCell table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata, SourceSpan
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.limits.definition import (
    _MAX_BLOCKS_PER_CELL,
    _MAX_COLUMNS,
    _MAX_ROWS,
)
from projectkoios.ingestion.tables.structure.limits.error import (
    TableStructureLimitError,
)
from projectkoios.ingestion.tables.structure.role.cell import TableCellRole
from projectkoios.ingestion.tables.structure.status.evidence import (
    TableStructureEvidenceStatus,
)


@dataclass(frozen=True)
class TableCell(AbstractTableStructureDataObject):
    cell_id: str
    structure_input_id: str
    candidate_id: str
    row_id: str
    page_index: int
    row_index: int
    column_index: int
    row_span: int
    column_span: int
    role: TableCellRole
    evidence_status: TableStructureEvidenceStatus
    proposed_text: str | None
    text_join_method: str | None
    source_texts: tuple[str, ...]
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    rendered_region_ids: tuple[str, ...]
    confidence: float
    evidence: Metadata
    warning_ids: tuple[str, ...]
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
        row_id: str,
        page_index: int,
        row_index: int,
        column_index: int,
        row_span: int,
        column_span: int,
        role: TableCellRole,
        evidence_status: TableStructureEvidenceStatus,
        proposed_text: str | None,
        text_join_method: str | None,
        source_texts: tuple[str, ...],
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        rendered_region_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableCell:
        normalized_confidence = cls._validated_parts(
            structure_input_id,
            candidate_id,
            row_id,
            page_index,
            row_index,
            column_index,
            row_span,
            column_span,
            role,
            evidence_status,
            proposed_text,
            text_join_method,
            source_texts,
            source_block_ids,
            source_spans,
            rendered_region_ids,
            confidence,
            evidence,
            warning_ids,
            processor_name,
            processor_version,
            configuration_digest,
        )
        cell_id = cls._derived_id(
            structure_input_id,
            candidate_id,
            row_id,
            page_index,
            row_index,
            column_index,
            row_span,
            column_span,
            role,
            evidence_status,
            proposed_text,
            text_join_method,
            source_texts,
            source_block_ids,
            source_spans,
            rendered_region_ids,
            normalized_confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            cell_id=cell_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            row_id=row_id,
            page_index=page_index,
            row_index=row_index,
            column_index=column_index,
            row_span=row_span,
            column_span=column_span,
            role=role,
            evidence_status=evidence_status,
            proposed_text=proposed_text,
            text_join_method=text_join_method,
            source_texts=source_texts,
            source_block_ids=source_block_ids,
            source_spans=source_spans,
            rendered_region_ids=rendered_region_ids,
            confidence=normalized_confidence,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table cell version")
        confidence = self._validated_parts(
            self.structure_input_id,
            self.candidate_id,
            self.row_id,
            self.page_index,
            self.row_index,
            self.column_index,
            self.row_span,
            self.column_span,
            self.role,
            self.evidence_status,
            self.proposed_text,
            self.text_join_method,
            self.source_texts,
            self.source_block_ids,
            self.source_spans,
            self.rendered_region_ids,
            self.confidence,
            self.evidence,
            self.warning_ids,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "confidence", confidence)
        if self.cell_id != self._derived_id(
            self.structure_input_id,
            self.candidate_id,
            self.row_id,
            self.page_index,
            self.row_index,
            self.column_index,
            self.row_span,
            self.column_span,
            self.role,
            self.evidence_status,
            self.proposed_text,
            self.text_join_method,
            self.source_texts,
            self.source_block_ids,
            self.source_spans,
            self.rendered_region_ids,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table cell ID is inconsistent")

    @classmethod
    def _validated_parts(
        cls,
        structure_input_id: str,
        candidate_id: str,
        row_id: str,
        page_index: int,
        row_index: int,
        column_index: int,
        row_span: int,
        column_span: int,
        role: TableCellRole,
        evidence_status: TableStructureEvidenceStatus,
        proposed_text: str | None,
        text_join_method: str | None,
        source_texts: tuple[str, ...],
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        rendered_region_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> float:
        cls._validate_identity_fields(
            structure_input_id,
            candidate_id,
            row_id,
            processor_name,
            processor_version,
            configuration_digest,
        )
        cls._validate_nonnegative_integer("cell page index", page_index)
        cls._validate_nonnegative_integer("cell row index", row_index)
        cls._validate_nonnegative_integer("cell column index", column_index)
        cls._validate_positive_integer("cell row span", row_span)
        cls._validate_positive_integer("cell column span", column_span)
        if row_span > _MAX_ROWS or column_span > _MAX_COLUMNS:
            raise TableStructureLimitError("cell span exceeds its hard limit")
        if not isinstance(role, TableCellRole):
            raise TypeError("cell role is unsupported")
        if not isinstance(evidence_status, TableStructureEvidenceStatus):
            raise TypeError("cell evidence status is unsupported")
        if proposed_text is not None:
            cls._validate_bounded_text("cell proposed text", proposed_text)
        if text_join_method is not None:
            cls._validate_bounded_string(
                "cell text join method", text_join_method, nonempty=True
            )
        if not isinstance(source_texts, tuple):
            raise TypeError("cell source texts must be an immutable tuple")
        for text in source_texts:
            cls._validate_bounded_text("cell source text", text)
        cls._validate_unique_strings("cell source block IDs", source_block_ids)
        if len(source_block_ids) > _MAX_BLOCKS_PER_CELL:
            raise TableStructureLimitError(
                "cell source blocks exceed their hard limit"
            )
        if len(source_texts) != len(source_block_ids):
            raise ValueError("cell source texts and blocks must align")
        if source_spans:
            cls._validate_spans(source_spans)
        elif source_block_ids:
            raise ValueError("source-backed cell requires source spans")
        cls._validate_unique_strings(
            "cell rendered region IDs", rendered_region_ids, required=True
        )
        cls._validate_unique_strings("cell warning IDs", warning_ids)
        cls._validate_metadata(evidence)
        return cls._validate_unit_float("cell confidence", confidence)

    @staticmethod
    def _derived_id(
        structure_input_id: str,
        candidate_id: str,
        row_id: str,
        page_index: int,
        row_index: int,
        column_index: int,
        row_span: int,
        column_span: int,
        role: TableCellRole,
        evidence_status: TableStructureEvidenceStatus,
        proposed_text: str | None,
        text_join_method: str | None,
        source_texts: tuple[str, ...],
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        rendered_region_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> str:
        return stable_id(
            "table-cell",
            structure_input_id,
            candidate_id,
            row_id,
            page_index,
            row_index,
            column_index,
            row_span,
            column_span,
            role.value,
            evidence_status.value,
            proposed_text,
            text_join_method,
            source_texts,
            source_block_ids,
            tuple(span.identity_parts() for span in source_spans),
            rendered_region_ids,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
