from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.image.png import EquationPngImage
from projectkoios.ingestion.sha256.verifier import SHA256Verifier


def test__equation_png_image__retains_exact_identified_bytes(
    png_bytes: bytes,
) -> None:
    image = EquationPngImage(
        source_ids=("rendered-region:png",),
        content=png_bytes,
    )

    assert image.media_type == "image/png"
    assert image.content is png_bytes
    assert SHA256Verifier.verify(
        content=png_bytes, expected=image.content_sha256
    )
    assert image.byte_length == len(png_bytes)
    assert hash(image)


def test__equation_png_image__rejects_non_png_bytes() -> None:
    with pytest.raises(ValueError, match="not a bounded PNG"):
        EquationPngImage(
            source_ids=("rendered-region:not-png",),
            content=b"not a png",
        )
