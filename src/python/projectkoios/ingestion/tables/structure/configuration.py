"""TableStructureConfiguration table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.bounds import (
    _MAX_ASSOCIATIONS,
    _MAX_BLOCKS_PER_CELL,
    _MAX_CANDIDATES,
    _MAX_CELLS,
    _MAX_COLUMNS,
    _MAX_CONTINUATIONS,
    _MAX_REGIONS,
    _MAX_RESULT_BYTES,
    _MAX_ROWS,
    _MAX_SOURCE_SPANS,
    _MAX_TEXT_CHARACTERS,
    _MAX_WARNINGS,
)
from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)


@dataclass(frozen=True)
class TableStructureConfiguration(AbstractTableStructureDataObject):
    max_candidates: int = _MAX_CANDIDATES
    max_regions: int = _MAX_REGIONS
    max_columns: int = _MAX_COLUMNS
    max_rows: int = _MAX_ROWS
    max_cells: int = _MAX_CELLS
    max_blocks_per_cell: int = _MAX_BLOCKS_PER_CELL
    max_source_spans: int = _MAX_SOURCE_SPANS
    max_associations: int = _MAX_ASSOCIATIONS
    max_continuations: int = _MAX_CONTINUATIONS
    max_warnings: int = _MAX_WARNINGS
    max_text_characters: int = _MAX_TEXT_CHARACTERS
    max_result_bytes: int = _MAX_RESULT_BYTES
    proposed_confidence_threshold: float = 0.75

    def __post_init__(self) -> None:
        for name, hard_maximum in (
            ("max_candidates", _MAX_CANDIDATES),
            ("max_regions", _MAX_REGIONS),
            ("max_columns", _MAX_COLUMNS),
            ("max_rows", _MAX_ROWS),
            ("max_cells", _MAX_CELLS),
            ("max_blocks_per_cell", _MAX_BLOCKS_PER_CELL),
            ("max_source_spans", _MAX_SOURCE_SPANS),
            ("max_associations", _MAX_ASSOCIATIONS),
            ("max_continuations", _MAX_CONTINUATIONS),
            ("max_warnings", _MAX_WARNINGS),
            ("max_text_characters", _MAX_TEXT_CHARACTERS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        ):
            value = getattr(self, name)
            self._validate_positive_integer(name, value)
            if value > hard_maximum:
                raise TableStructureLimitError(
                    f"{name} exceeds its implementation maximum "
                    f"({hard_maximum})"
                )
        object.__setattr__(
            self,
            "proposed_confidence_threshold",
            self._validate_unit_float(
                "proposed_confidence_threshold",
                self.proposed_confidence_threshold,
            ),
        )

    @property
    def configuration_digest(self) -> str:
        return stable_id("table-structure-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )
