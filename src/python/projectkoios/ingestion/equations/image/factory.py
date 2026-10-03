"""Closed factory for exact equation-image representations."""

from __future__ import annotations

from projectkoios.ingestion.equations.image.base import AbstractEquationImage
from projectkoios.ingestion.equations.image.jpeg import EquationJpegImage
from projectkoios.ingestion.equations.image.png import EquationPngImage
from projectkoios.ingestion.equations.image.webp import EquationWebpImage


class EquationImageFormatError(ValueError):
    """Raised when equation-image bytes have no supported exact format."""


class EquationImage:
    """Non-instantiable convenience factory for concrete image values."""

    __slots__ = ()

    def __new__(cls) -> EquationImage:
        raise TypeError("EquationImage is a factory; use from_bytes()")

    @classmethod
    def from_bytes(
        cls,
        *,
        content: bytes,
        source_ids: tuple[str, ...],
        expected_media_type: str | None = None,
    ) -> AbstractEquationImage:
        """Return the nominal image type detected from exact bounded bytes."""

        if type(content) is not bytes:
            raise TypeError("equation image content must be bytes")
        if (
            not content
            or len(content) > AbstractEquationImage.MAX_CONTENT_BYTES
        ):
            raise ValueError("equation image content size is out of bounds")
        if (
            expected_media_type is not None
            and type(expected_media_type) is not str
        ):
            raise TypeError("expected_media_type must be a string or None")

        image: AbstractEquationImage
        if content.startswith(EquationPngImage.PNG_SIGNATURE):
            image = EquationPngImage(source_ids=source_ids, content=content)
        elif content.startswith(EquationJpegImage.JPEG_START):
            image = EquationJpegImage(source_ids=source_ids, content=content)
        elif (
            len(content) >= 12
            and content[:4] == EquationWebpImage.RIFF_SIGNATURE
            and content[8:12] == EquationWebpImage.WEBP_SIGNATURE
        ):
            image = EquationWebpImage(source_ids=source_ids, content=content)
        else:
            raise EquationImageFormatError(
                "equation image format is unsupported"
            )
        if (
            expected_media_type is not None
            and expected_media_type != image.media_type
        ):
            raise EquationImageFormatError(
                "equation image media type does not match its content"
            )
        return image
