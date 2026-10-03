from __future__ import annotations

import hashlib

import pytest
from projectkoios.ingestion.equations.image.jpeg import EquationJpegImage


def test__equation_jpeg_image__retains_exact_identified_bytes(
    jpeg_bytes: bytes,
) -> None:
    image = EquationJpegImage(
        source_ids=("rendered-region:jpeg",),
        content=jpeg_bytes,
    )

    assert image.media_type == "image/jpeg"
    assert image.content is jpeg_bytes
    assert image.content_sha256 == hashlib.sha256(jpeg_bytes).hexdigest()


def test__equation_jpeg_image__rejects_non_jpeg_bytes() -> None:
    with pytest.raises(ValueError, match="not a bounded JPEG"):
        EquationJpegImage(
            source_ids=("rendered-region:not-jpeg",),
            content=b"not a jpeg",
        )
