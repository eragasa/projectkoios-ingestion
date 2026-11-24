"""One ordered row in an exact table-evidence proposal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.cell import (
    TableEvidenceProposalCell,
)
from projectkoios.ingestion.tables.acceptance.validation import (
    require_id,
    require_row_index,
    require_text,
)


@dataclass(frozen=True, slots=True)
class TableEvidenceProposalRow(AbstractImmutableDataObject):
    """Bind one compound label to a complete ordered cell tuple."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-proposal-row"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    row_index: int
    compound: str
    cells: tuple[TableEvidenceProposalCell, ...]
    row_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported table-evidence row contract")
        require_row_index("row_index", self.row_index)
        require_text("compound", self.compound, identity=True)
        if not isinstance(self.cells, tuple) or not self.cells:
            raise ValueError("cells must be a non-empty immutable tuple")
        if any(
            type(cell) is not TableEvidenceProposalCell for cell in self.cells
        ):
            raise TypeError("row cells contain an unsupported value")
        if tuple(cell.row_index for cell in self.cells) != (
            self.row_index,
        ) * len(self.cells):
            raise ValueError("row cell indices disagree with the row")
        if tuple(cell.parameter_index for cell in self.cells) != tuple(
            range(len(self.cells))
        ):
            raise ValueError("row cells must have contiguous parameter order")
        object.__setattr__(
            self,
            "row_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.row_index,
                self.compound,
                tuple(cell.cell_id for cell in self.cells),
            ),
        )
        require_id("row_id", self.row_id, self.CONTRACT_NAME)
