from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.image.jpeg import EquationJpegImage
from projectkoios.ingestion.sha256.verifier import SHA256Verifier


def test__equation_jpeg_image__retains_exact_identified_bytes(
    jpeg_bytes: bytes,
) -> None:
    image = EquationJpegImage(
        source_ids=("rendered-region:jpeg",),
        content=jpeg_bytes,
    )

    assert image.media_type == "image/jpeg"
    assert image.content is jpeg_bytes
    assert SHA256Verifier.verify(
        content=jpeg_bytes, expected=image.content_sha256
    )


def test__equation_jpeg_image__rejects_non_jpeg_bytes() -> None:
    with pytest.raises(ValueError, match="not a bounded JPEG"):
        EquationJpegImage(
            source_ids=("rendered-region:not-jpeg",),
            content=b"not a jpeg",
        )
