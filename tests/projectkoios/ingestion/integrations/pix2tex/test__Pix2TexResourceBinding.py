from pathlib import Path

import pytest
from projectkoios.ingestion.integrations.pix2tex.resource import (
    Pix2TexResourceBinding,
)


def test__pix2tex_resource_binding__requires_portable_name_and_named_path(
    tmp_path: Path,
) -> None:
    binding = Pix2TexResourceBinding(
        name="model.weights",
        path=tmp_path / "model",
    )

    assert binding.name == "model.weights"
    assert binding.path.name == "model"
    with pytest.raises(ValueError, match="portable"):
        Pix2TexResourceBinding(name="model weights", path=tmp_path / "model")
