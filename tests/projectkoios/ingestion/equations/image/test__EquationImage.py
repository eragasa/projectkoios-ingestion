from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.image.factory import EquationImage
from projectkoios.ingestion.equations.image.jpeg import EquationJpegImage
from projectkoios.ingestion.equations.image.png import EquationPngImage
from projectkoios.ingestion.equations.image.webp import EquationWebpImage


def test__equation_image__dispatches_to_nominal_format_classes(
    png_bytes: bytes,
    jpeg_bytes: bytes,
    webp_bytes: bytes,
) -> None:
    source_ids = ("rendered-region:factory",)

    assert type(
        EquationImage.from_bytes(content=png_bytes, source_ids=source_ids)
    ) is EquationPngImage
    assert type(
        EquationImage.from_bytes(content=jpeg_bytes, source_ids=source_ids)
    ) is EquationJpegImage
    assert type(
        EquationImage.from_bytes(content=webp_bytes, source_ids=source_ids)
    ) is EquationWebpImage


def test__equation_image__cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="factory"):
        EquationImage()
