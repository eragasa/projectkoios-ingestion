"""Immutable deterministic derivation for one table candidate."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from projectkoios.ingestion.models import Metadata
from projectkoios.ingestion.tables.contracts import (
    TableBoundaryKind,
    TableCandidate,
    TableEvidenceStatus,
)
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.cell import TableCell
from projectkoios.ingestion.tables.structure.column_derivation import (
    TableColumnDerivation,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.continuation_derivation import (
    TableContinuationDerivation,
)
from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)
from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)
from projectkoios.ingestion.tables.structure.region_derivation import (
    TableRegionDerivation,
)
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)
from projectkoios.ingestion.tables.structure.row import TableRow
from projectkoios.ingestion.tables.structure.structure import TableStructure
from projectkoios.ingestion.tables.structure.warning_specification import (
    TableStructureWarningSpecification,
)


@dataclass(frozen=True)
class TableStructureDerivation(AbstractTableStructureDataObject):
    """Represent the complete deterministic derivation of one candidate."""

    CONTRACT_NAME: ClassVar[str] = "table-structure-derivation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    structure: TableStructure
    warning_specifications: tuple[TableStructureWarningSpecification, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.structure, TableStructure):
            raise TypeError("structure derivation requires a TableStructure")
        if not isinstance(self.warning_specifications, tuple) or any(
            not isinstance(item, TableStructureWarningSpecification)
            for item in self.warning_specifications
        ):
            raise TypeError(
                "structure derivation requires immutable warning specifications"
            )

    @classmethod
    def create(
        cls,
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        processor_name: str,
        processor_version: str,
    ) -> TableStructureDerivation:
        configuration = structure_input.configuration
        column_derivation = TableColumnDerivation.create(
            structure_input=structure_input,
            candidate=candidate,
            processor_name=processor_name,
            processor_version=processor_version,
        )
        rows, cells, warnings = cls._derive_regions(
            structure_input=structure_input,
            candidate=candidate,
            column_derivation=column_derivation,
            processor_name=processor_name,
            processor_version=processor_version,
        )
        continuations = TableContinuationDerivation.create(
            structure_input=structure_input,
            candidate=candidate,
            processor_name=processor_name,
            processor_version=processor_version,
        ).continuations
        cls._validate_derived_counts(structure_input, rows, cells)
        if candidate.confidence < configuration.proposed_confidence_threshold:
            warnings += (
                TableStructureWarningSpecification(
                    code="table_structure.low_confidence",
                    message=(
                        "Source candidate confidence is below the configured "
                        "structure-proposal threshold"
                    ),
                    object_ids=(),
                    source_spans=candidate.source_spans,
                ),
            )
        ambiguous = (
            bool(warnings)
            or candidate.evidence_status is TableEvidenceStatus.AMBIGUOUS
        )
        evidence: Metadata = (
            ("column_count", str(len(column_derivation.columns))),
            ("row_count", str(len(rows))),
            ("cell_count", str(len(cells))),
            ("continuation_count", str(len(continuations))),
        )
        structure = TableStructure.create(
            structure_input_id=structure_input.input_id,
            candidate_id=candidate.candidate_id,
            source_label=candidate.source_label,
            boundary_kind=candidate.boundary_kind,
            evidence_status=(
                TableStructureEvidenceStatus.AMBIGUOUS
                if ambiguous
                else TableStructureEvidenceStatus.PROPOSED
            ),
            columns=column_derivation.columns,
            rows=rows,
            cells=cells,
            continuations=continuations,
            association_ids=tuple(
                association.association_id
                for association in candidate.associations
            ),
            confidence=cls._confidence(candidate, ambiguous),
            evidence=evidence,
            warning_ids=(),
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration.configuration_digest,
        )
        warnings = tuple(
            replace(
                warning,
                object_ids=(structure.structure_id, *warning.object_ids),
            )
            for warning in warnings
        )
        if candidate.evidence_status is TableEvidenceStatus.AMBIGUOUS:
            warnings += (
                TableStructureWarningSpecification(
                    code="table_structure.ambiguous_candidate_inherited",
                    message="The source table candidate is ambiguous",
                    object_ids=(structure.structure_id,),
                    source_spans=candidate.source_spans,
                ),
            )
        return cls(
            structure=structure,
            warning_specifications=warnings,
        )

    @staticmethod
    def _derive_regions(
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        column_derivation: TableColumnDerivation,
        processor_name: str,
        processor_version: str,
    ) -> tuple[
        tuple[TableRow, ...],
        tuple[TableCell, ...],
        tuple[TableStructureWarningSpecification, ...],
    ]:
        rows: list[TableRow] = []
        cells: list[TableCell] = []
        warnings: list[TableStructureWarningSpecification] = []
        first_header_texts: tuple[str, ...] | None = None
        reading_order = 0
        for region, boundaries in zip(
            candidate.regions,
            column_derivation.region_boundaries,
            strict=True,
        ):
            derivation = TableRegionDerivation.create(
                structure_input=structure_input,
                candidate=candidate,
                region=region,
                column_boundaries=boundaries,
                column_count=len(column_derivation.columns),
                first_header_texts=first_header_texts,
                reading_order=reading_order,
                processor_name=processor_name,
                processor_version=processor_version,
            )
            rows.extend(derivation.rows)
            cells.extend(derivation.cells)
            warnings.extend(derivation.warning_specifications)
            first_header_texts = derivation.first_header_texts
            reading_order = derivation.next_reading_order
        return tuple(rows), tuple(cells), tuple(warnings)

    @staticmethod
    def _validate_derived_counts(
        structure_input: TableStructureRequest,
        rows: tuple[TableRow, ...],
        cells: tuple[TableCell, ...],
    ) -> None:
        if len(rows) > structure_input.configuration.max_rows:
            raise TableStructureLimitError("rows exceed max_rows")
        if len(cells) > structure_input.configuration.max_cells:
            raise TableStructureLimitError("cells exceed max_cells")

    @staticmethod
    def _confidence(candidate: TableCandidate, ambiguous: bool) -> float:
        return max(
            0.0,
            candidate.confidence
            - (0.15 if ambiguous else 0.0)
            - (
                0.05
                if candidate.boundary_kind is TableBoundaryKind.UNRULED
                else 0.0
            ),
        )
