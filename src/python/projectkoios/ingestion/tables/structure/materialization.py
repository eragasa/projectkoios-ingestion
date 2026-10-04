"""Immutable materialization of table-structure warning links."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from projectkoios.ingestion.models import IngestionWarning, WarningSeverity
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.structure import TableStructure
from projectkoios.ingestion.tables.structure.warning_specification import (
    TableStructureWarningSpecification,
)


@dataclass(frozen=True)
class TableStructureMaterialization(AbstractTableStructureDataObject):
    """Represent warning publication and linked final structures."""

    CONTRACT_NAME: ClassVar[str] = "table-structure-materialization"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    warnings: tuple[IngestionWarning, ...]
    structures: tuple[TableStructure, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.warnings, tuple) or any(
            not isinstance(item, IngestionWarning) for item in self.warnings
        ):
            raise TypeError("materialization requires immutable warnings")
        if not isinstance(self.structures, tuple) or any(
            not isinstance(item, TableStructure) for item in self.structures
        ):
            raise TypeError("materialization requires immutable structures")

    @classmethod
    def create(
        cls,
        *,
        structures: tuple[TableStructure, ...],
        warning_specifications: tuple[
            tuple[TableStructureWarningSpecification, ...], ...
        ],
    ) -> TableStructureMaterialization:
        warnings: list[IngestionWarning] = []
        by_object: dict[str, list[str]] = {}
        for specifications in warning_specifications:
            for specification in specifications:
                warning = IngestionWarning.create(
                    code=specification.code,
                    severity=WarningSeverity.WARNING,
                    message=specification.message,
                    object_ids=specification.object_ids,
                    source_spans=specification.source_spans,
                    evidence=specification.evidence,
                )
                warnings.append(warning)
                for object_id in warning.object_ids:
                    by_object.setdefault(object_id, []).append(
                        warning.warning_id
                    )
        final_structures = tuple(
            replace(
                structure,
                cells=tuple(
                    replace(
                        cell,
                        warning_ids=tuple(by_object.get(cell.cell_id, ())),
                    )
                    for cell in structure.cells
                ),
                warning_ids=tuple(by_object.get(structure.structure_id, ())),
            )
            for structure in structures
        )
        return cls(warnings=tuple(warnings), structures=final_structures)
