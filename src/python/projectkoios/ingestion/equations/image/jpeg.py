"""Exact JPEG equation-image representation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.equations.image.base import AbstractEquationImage


@dataclass(frozen=True, slots=True)
class EquationJpegImage(AbstractEquationImage):
    """One exact bounded JPEG representation of equation evidence."""

    CONTRACT_NAME: ClassVar[str] = "equation-jpeg-image"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    JPEG_START: ClassVar[bytes] = b"\xff\xd8\xff"
    JPEG_END: ClassVar[bytes] = b"\xff\xd9"

    @property
    def media_type(self) -> str:
        return "image/jpeg"

    def _validate_format(self) -> None:
        if (
            len(self.content) < 4
            or not self.content.startswith(EquationJpegImage.JPEG_START)
            or not self.content.endswith(EquationJpegImage.JPEG_END)
        ):
            raise ValueError("equation image is not a bounded JPEG")
