from __future__ import annotations

import hashlib

import pytest
from projectkoios.ingestion.equations.image.png import EquationPngImage


def test__equation_png_image__retains_exact_identified_bytes(
    png_bytes: bytes,
) -> None:
    image = EquationPngImage(
        source_ids=("rendered-region:png",),
        content=png_bytes,
    )

    assert image.media_type == "image/png"
    assert image.content is png_bytes
    assert image.content_sha256 == hashlib.sha256(png_bytes).hexdigest()
    assert image.byte_length == len(png_bytes)
    assert hash(image)


def test__equation_png_image__rejects_non_png_bytes() -> None:
    with pytest.raises(ValueError, match="not a bounded PNG"):
        EquationPngImage(
            source_ids=("rendered-region:not-png",),
            content=b"not a png",
        )
