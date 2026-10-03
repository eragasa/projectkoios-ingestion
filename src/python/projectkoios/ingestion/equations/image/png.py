"""Exact PNG equation-image representation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.equations.image.base import AbstractEquationImage


@dataclass(frozen=True, slots=True)
class EquationPngImage(AbstractEquationImage):
    """One exact bounded PNG representation of equation evidence."""

    CONTRACT_NAME: ClassVar[str] = "equation-png-image"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    PNG_SIGNATURE: ClassVar[bytes] = b"\x89PNG\r\n\x1a\n"
    PNG_IEND: ClassVar[bytes] = b"\x00\x00\x00\x00IEND\xaeB`\x82"

    @property
    def media_type(self) -> str:
        return "image/png"

    def _validate_format(self) -> None:
        if (
            len(self.content) < 33
            or not self.content.startswith(EquationPngImage.PNG_SIGNATURE)
            or self.content[12:16] != b"IHDR"
            or int.from_bytes(self.content[16:20], "big") <= 0
            or int.from_bytes(self.content[20:24], "big") <= 0
            or not self.content.endswith(EquationPngImage.PNG_IEND)
        ):
            raise ValueError("equation image is not a bounded PNG")
