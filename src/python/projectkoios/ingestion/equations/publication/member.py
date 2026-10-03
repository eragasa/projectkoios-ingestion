"""One named equation publication member."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from projectkoios.ingestion.base import AbstractImmutableDataObject


class EquationPublicationMemberName(StrEnum):
    """Closed names in one equation publication set."""

    ASSEMBLY = "assembly"
    RECOGNITION = "recognition"
    INDEX = "index"
    DERIVATION = "derivation"


@dataclass(frozen=True, slots=True)
class EquationPublicationMember(AbstractImmutableDataObject):
    """One exact destination and serialized publication payload."""

    name: EquationPublicationMemberName
    path: Path
    content: str

    def __post_init__(self) -> None:
        if type(self.name) is not EquationPublicationMemberName:
            raise TypeError("equation publication member name is invalid")
        if not isinstance(self.path, Path) or not self.path.name:
            raise TypeError("equation publication member path is invalid")
        if type(self.content) is not str or not self.content.endswith("\n"):
            raise ValueError(
                "equation publication member must contain newline JSON"
            )
