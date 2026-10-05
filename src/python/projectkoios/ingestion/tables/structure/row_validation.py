"""Immutable validation evidence for derived table rows."""

from __future__ import annotations

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
class TableRowValidation(AbstractTableStructureDataObject, AbstractValidation):
    """Record successful cross-object validation of derived rows."""

    CONTRACT_NAME: ClassVar[str] = "table-row-validation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    structure_id: str
    validated_row_count: int

    def __post_init__(self) -> None:
        self._validate_identity_fields(self.structure_id)
        self._validate_nonnegative_integer(
            "validated row count", self.validated_row_count
        )

    @classmethod
    def create(
        cls,
        *,
        structure: TableStructure,
        regions: tuple[TableRegionEvidence, ...],
    ) -> TableRowValidation:
        if tuple(row.reading_order for row in structure.rows) != tuple(
            range(len(structure.rows))
        ):
            raise ValueError("structure row order is not contiguous")
        region_by_id = {region.region_evidence_id: region for region in regions}
        page_row_indexes: dict[str, list[int]] = {
            region_id: [] for region_id in region_by_id
        }
        for row in structure.rows:
            region = region_by_id.get(row.region_id)
            if region is None or row.page_index != region.page_index:
                raise ValueError("row region evidence is inconsistent")
            if (
                row.structure_input_id != structure.structure_input_id
                or row.candidate_id != structure.candidate_id
                or row.processor_name != structure.processor_name
                or row.processor_version != structure.processor_version
                or row.configuration_digest != structure.configuration_digest
            ):
                raise ValueError("row derivation evidence is inconsistent")
            page_row_indexes[row.region_id].append(row.page_row_index)
            x0, y0, x1, y1 = row.source_bounding_box
            rx0, ry0, rx1, ry1 = region.source_bounding_box
            if x0 < rx0 or y0 < ry0 or x1 > rx1 or y1 > ry1:
                raise ValueError("row bounds exceed the candidate region")
        if any(
            tuple(indexes) != tuple(range(len(indexes)))
            for indexes in page_row_indexes.values()
        ):
            raise ValueError("page-local row indexes are not contiguous")
        return cls(
            structure_id=structure.structure_id,
            validated_row_count=len(structure.rows),
        )
