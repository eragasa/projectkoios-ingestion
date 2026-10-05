"""Named create-once filesystem artifact publication item."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


@dataclass(frozen=True, slots=True)
class ArtifactPublicationItem(AbstractImmutableDataObject):
    """One explicit filesystem destination and serialized text payload."""

    path: Path
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.name:
            raise TypeError("artifact publication path is invalid")
        if type(self.text) is not str:
            raise TypeError("artifact publication text must be a string")
