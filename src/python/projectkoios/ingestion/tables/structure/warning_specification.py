"""TableStructureWarningSpecification table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.models import Metadata, SourceSpan
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)


@dataclass(frozen=True)
class TableStructureWarningSpecification(AbstractTableStructureDataObject):
    CONTRACT_NAME: ClassVar[str] = "table-structure-warning-specification"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    code: str
    message: str
    object_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    evidence: Metadata = ()

    def __post_init__(self) -> None:
        self._validate_bounded_string("warning code", self.code, nonempty=True)
        self._validate_bounded_string(
            "warning message", self.message, nonempty=True
        )
        self._validate_unique_strings("warning object IDs", self.object_ids)
        if not isinstance(self.source_spans, tuple) or any(
            not isinstance(item, SourceSpan) for item in self.source_spans
        ):
            raise TypeError("warning source spans must be an immutable tuple")
        self._validate_metadata(self.evidence)
