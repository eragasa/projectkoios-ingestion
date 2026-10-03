"""Exact WebP equation-image representation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.equations.image.base import AbstractEquationImage


@dataclass(frozen=True, slots=True)
class EquationWebpImage(AbstractEquationImage):
    """One exact bounded WebP representation of equation evidence."""

    CONTRACT_NAME: ClassVar[str] = "equation-webp-image"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    RIFF_SIGNATURE: ClassVar[bytes] = b"RIFF"
    WEBP_SIGNATURE: ClassVar[bytes] = b"WEBP"

    @property
    def media_type(self) -> str:
        return "image/webp"

    def _validate_format(self) -> None:
        declared_size = (
            int.from_bytes(self.content[4:8], "little") + 8
            if len(self.content) >= 12
            else -1
        )
        if (
            len(self.content) < 20
            or not self.content.startswith(EquationWebpImage.RIFF_SIGNATURE)
            or not self.content.startswith(
                EquationWebpImage.WEBP_SIGNATURE,
                8,
            )
            or declared_size != len(self.content)
        ):
            raise ValueError("equation image is not a bounded WebP")
