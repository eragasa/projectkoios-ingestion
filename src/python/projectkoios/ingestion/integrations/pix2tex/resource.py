"""Named Pix2Tex resource binding."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


@dataclass(frozen=True, slots=True)
class Pix2TexResourceBinding(AbstractImmutableDataObject):
    """One portable resource name bound to one local path."""

    name: str
    path: Path

    def __post_init__(self) -> None:
        if type(self.name) is not str or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9._-]*",
            self.name,
        ):
            raise ValueError("Pix2Tex resource name must be portable")
        if not isinstance(self.path, Path) or not self.path.name:
            raise TypeError("Pix2Tex resource path is invalid")
