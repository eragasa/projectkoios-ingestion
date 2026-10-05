"""Immutable validation evidence for derived table columns."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.tables.contracts import TableRegionEvidence
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.structure import TableStructure


@dataclass(frozen=True)
class TableColumnValidation(
    AbstractTableStructureDataObject, AbstractValidation
):
    """Record successful cross-object validation of derived columns."""

    CONTRACT_NAME: ClassVar[str] = "table-column-validation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    structure_id: str
    validated_column_count: int

    def __post_init__(self) -> None:
        self._validate_identity_fields(self.structure_id)
        self._validate_nonnegative_integer(
            "validated column count", self.validated_column_count
        )

    @classmethod
    def create(
        cls,
        *,
        structure: TableStructure,
        regions: tuple[TableRegionEvidence, ...],
    ) -> TableColumnValidation:
        if tuple(column.column_index for column in structure.columns) != tuple(
            range(len(structure.columns))
        ):
            raise ValueError("structure columns are not contiguous")
        expected_region_ids = tuple(
            region.region_evidence_id for region in regions
        )
        for index, column in enumerate(structure.columns):
            if (
                column.structure_input_id != structure.structure_input_id
                or column.candidate_id != structure.candidate_id
                or column.processor_name != structure.processor_name
                or column.processor_version != structure.processor_version
                or column.configuration_digest != structure.configuration_digest
            ):
                raise ValueError("column derivation evidence is inconsistent")
            if column.source_region_ids != expected_region_ids:
                raise ValueError("column source regions are inconsistent")
            if index and not math.isclose(
                structure.columns[index - 1].normalized_right,
                column.normalized_left,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "normalized column boundaries are not contiguous"
                )
        return cls(
            structure_id=structure.structure_id,
            validated_column_count=len(structure.columns),
        )
