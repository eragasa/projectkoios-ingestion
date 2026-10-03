from __future__ import annotations

import pytest
from projectkoios.ingestion.equations.image.factory import (
    EquationImage,
    EquationImageFormatError,
)


def test__equation_image_format_error__rejects_unsupported_content() -> None:
    with pytest.raises(EquationImageFormatError, match="unsupported"):
        EquationImage.from_bytes(
            content=b"unsupported equation image",
            source_ids=("rendered-region:unsupported",),
        )


def test__equation_image_format_error__rejects_media_type_mismatch(
    png_bytes: bytes,
) -> None:
    with pytest.raises(EquationImageFormatError, match="does not match"):
        EquationImage.from_bytes(
            content=png_bytes,
            source_ids=("rendered-region:mismatch",),
            expected_media_type="image/jpeg",
        )
