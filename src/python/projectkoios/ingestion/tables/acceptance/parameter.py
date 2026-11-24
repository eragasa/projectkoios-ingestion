"""One ordered accepted-table parameter definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.acceptance.validation import (
    require_column_index,
    require_id,
    require_text,
)


@dataclass(frozen=True, slots=True)
class TableEvidenceParameter(AbstractImmutableDataObject):
    """Preserve one exact printed header, unit, and logical order."""

    CONTRACT_NAME: ClassVar[str] = "table-evidence-parameter"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    parameter_index: int
    parameter_key: str
    printed_header: str
    unit: str
    printed_panel: int
    parameter_id: str = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported table-evidence parameter contract")
        require_column_index("parameter_index", self.parameter_index)
        require_text("parameter_key", self.parameter_key, identity=True)
        require_text("printed_header", self.printed_header, identity=True)
        require_text("unit", self.unit, identity=True)
        if self.printed_panel not in (1, 2):
            raise ValueError("printed_panel must be one or two")
        object.__setattr__(
            self,
            "parameter_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.parameter_index,
                self.parameter_key,
                self.printed_header,
                self.unit,
                self.printed_panel,
            ),
        )
        require_id("parameter_id", self.parameter_id, self.CONTRACT_NAME)
