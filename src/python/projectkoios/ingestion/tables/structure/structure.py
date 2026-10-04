"""TableStructure table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata
from projectkoios.ingestion.tables.contracts import TableBoundaryKind
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.bounds import (
    _MAX_CELLS,
    _MAX_COLUMNS,
    _MAX_CONTINUATIONS,
    _MAX_ROWS,
)
from projectkoios.ingestion.tables.structure.cell import TableCell
from projectkoios.ingestion.tables.structure.column import TableColumn
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.continuation import (
    TableContinuation,
)
from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)
from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)
from projectkoios.ingestion.tables.structure.row import TableRow


@dataclass(frozen=True)
class TableStructure(AbstractTableStructureDataObject):
    structure_id: str
    structure_input_id: str
    candidate_id: str
    source_label: str | None
    boundary_kind: TableBoundaryKind
    evidence_status: TableStructureEvidenceStatus
    columns: tuple[TableColumn, ...]
    rows: tuple[TableRow, ...]
    cells: tuple[TableCell, ...]
    continuations: tuple[TableContinuation, ...]
    association_ids: tuple[str, ...]
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
        source_label: str | None,
        boundary_kind: TableBoundaryKind,
        evidence_status: TableStructureEvidenceStatus,
        columns: tuple[TableColumn, ...],
        rows: tuple[TableRow, ...],
        cells: tuple[TableCell, ...],
        continuations: tuple[TableContinuation, ...],
        association_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        warning_ids: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableStructure:
        normalized = cls._validated_parts(
            structure_input_id,
            candidate_id,
            source_label,
            boundary_kind,
            evidence_status,
            columns,
            rows,
            cells,
            continuations,
            association_ids,
            confidence,
            evidence,
            warning_ids,
            processor_name,
            processor_version,
            configuration_digest,
        )
        structure_id = cls._derived_id(
            structure_input_id,
            candidate_id,
            source_label,
            boundary_kind,
            evidence_status,
            columns,
            rows,
            cells,
            continuations,
            association_ids,
            normalized,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            structure_id=structure_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            source_label=source_label,
            boundary_kind=boundary_kind,
            evidence_status=evidence_status,
            columns=columns,
            rows=rows,
            cells=cells,
            continuations=continuations,
            association_ids=association_ids,
            confidence=normalized,
            evidence=evidence,
            warning_ids=warning_ids,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table structure version")
        confidence = self._validated_parts(
            self.structure_input_id,
            self.candidate_id,
            self.source_label,
            self.boundary_kind,
            self.evidence_status,
            self.columns,
            self.rows,
            self.cells,
            self.continuations,
            self.association_ids,
            self.confidence,
            self.evidence,
            self.warning_ids,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "confidence", confidence)
        if self.structure_id != self._derived_id(
            self.structure_input_id,
            self.candidate_id,
            self.source_label,
            self.boundary_kind,
            self.evidence_status,
            self.columns,
            self.rows,
            self.cells,
            self.continuations,
            self.association_ids,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table structure ID is inconsistent")

    @classmethod
    def _validated_parts(
        cls,
        structure_input_id: str,
        candidate_id: str,
        source_label: str | None,
        boundary_kind: TableBoundaryKind,
        evidence_status: TableStructureEvidenceStatus,
        columns: tuple[TableColumn, ...],
        rows: tuple[TableRow, ...],
        cells: tuple[TableCell, ...],
        continuations: tuple[TableContinuation, ...],
        association_ids: tuple[str, ...],
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
            processor_name,
            processor_version,
            configuration_digest,
        )
        if source_label is not None:
            cls._validate_bounded_string(
                "table source label", source_label, nonempty=True
            )
        if not isinstance(boundary_kind, TableBoundaryKind):
            raise TypeError("table boundary kind is unsupported")
        if not isinstance(evidence_status, TableStructureEvidenceStatus):
            raise TypeError("table structure evidence status is unsupported")
        for name, values, expected_type, hard_limit in (
            ("columns", columns, TableColumn, _MAX_COLUMNS),
            ("rows", rows, TableRow, _MAX_ROWS),
            ("cells", cells, TableCell, _MAX_CELLS),
            (
                "continuations",
                continuations,
                TableContinuation,
                _MAX_CONTINUATIONS,
            ),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be an immutable tuple")
            if not values and name in ("columns", "rows", "cells"):
                raise ValueError(f"table structure requires {name}")
            if len(values) > hard_limit:
                raise TableStructureLimitError(
                    f"{name} exceed their hard limit"
                )
            if any(not isinstance(item, expected_type) for item in values):
                raise TypeError(f"{name} contain an unsupported value")
        cls._validate_unique_strings(
            "structure association IDs", association_ids
        )
        cls._validate_unique_strings("structure warning IDs", warning_ids)
        cls._validate_metadata(evidence)
        return cls._validate_unit_float(
            "table structure confidence", confidence
        )

    @staticmethod
    def _derived_id(
        structure_input_id: str,
        candidate_id: str,
        source_label: str | None,
        boundary_kind: TableBoundaryKind,
        evidence_status: TableStructureEvidenceStatus,
        columns: tuple[TableColumn, ...],
        rows: tuple[TableRow, ...],
        cells: tuple[TableCell, ...],
        continuations: tuple[TableContinuation, ...],
        association_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> str:
        return stable_id(
            "table-structure",
            structure_input_id,
            candidate_id,
            source_label,
            boundary_kind.value,
            evidence_status.value,
            tuple(column.column_id for column in columns),
            tuple(row.row_id for row in rows),
            tuple(cell.cell_id for cell in cells),
            tuple(item.continuation_id for item in continuations),
            association_ids,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
