"""One exact source-backed table proposal cell."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.validation import (
    require_box,
    require_column_index,
    require_decimal_text,
    require_id,
    require_row_index,
    require_string_tuple,
    require_text,
)

_ALLOWED_AMBIGUITY_FLAGS = frozenset(
    {"native-render-disagreement", "independent-ocr-disagreement"}
)


@dataclass(frozen=True, slots=True)
class TableEvidenceProposalCell(AbstractImmutableDataObject):
    """Retain proposed text separately from raw native and OCR observations."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-proposal-cell"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    row_index: int
    parameter_index: int
    parameter_key: str
    printed_header: str
    unit: str
    printed_panel: int
    raw_native_text: str
    proposed_text: str
    source_bounding_box: tuple[float, float, float, float]
    independent_ocr_text: str
    ambiguity_flags: tuple[str, ...]
    cell_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported table-evidence cell contract")
        require_row_index("row_index", self.row_index)
        require_column_index("parameter_index", self.parameter_index)
        require_text("parameter_key", self.parameter_key, identity=True)
        require_text("printed_header", self.printed_header, identity=True)
        require_text("unit", self.unit, identity=True)
        if self.printed_panel not in (1, 2):
            raise ValueError("printed_panel must be one or two")
        require_text("raw_native_text", self.raw_native_text)
        require_decimal_text("proposed_text", self.proposed_text)
        object.__setattr__(
            self,
            "source_bounding_box",
            require_box("source_bounding_box", self.source_bounding_box),
        )
        require_text("independent_ocr_text", self.independent_ocr_text)
        require_string_tuple(
            "ambiguity_flags", self.ambiguity_flags, unique=True
        )
        if not set(self.ambiguity_flags) <= _ALLOWED_AMBIGUITY_FLAGS:
            raise ValueError("cell contains an unsupported ambiguity flag")
        object.__setattr__(
            self,
            "cell_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.row_index,
                self.parameter_index,
                self.parameter_key,
                self.printed_header,
                self.unit,
                self.printed_panel,
                self.raw_native_text,
                self.proposed_text,
                self.source_bounding_box,
                self.independent_ocr_text,
                self.ambiguity_flags,
            ),
        )
        require_id("cell_id", self.cell_id, self.CONTRACT_NAME)
