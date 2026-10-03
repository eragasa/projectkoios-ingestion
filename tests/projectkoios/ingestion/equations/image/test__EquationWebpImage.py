from __future__ import annotations

import hashlib

import pytest
from projectkoios.ingestion.equations.image.webp import EquationWebpImage


def test__equation_webp_image__retains_exact_identified_bytes(
    webp_bytes: bytes,
) -> None:
    image = EquationWebpImage(
        source_ids=("rendered-region:webp",),
        content=webp_bytes,
    )

    assert image.media_type == "image/webp"
    assert image.content is webp_bytes
    assert image.content_sha256 == hashlib.sha256(webp_bytes).hexdigest()


def test__equation_webp_image__rejects_inconsistent_riff_size() -> None:
    with pytest.raises(ValueError, match="not a bounded WebP"):
        EquationWebpImage(
            source_ids=("rendered-region:bad-webp",),
            content=b"RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00",
        )
