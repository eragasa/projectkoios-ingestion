from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest
from conftest import _region
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalSelection,
)


def test__selection__binds_exact_rendered_evidence() -> None:
    region = _region()
    selection = OllamaMultimodalSelection.from_rendered_region(region)

    assert selection.rendered_region is region
    assert selection.selection_id == selection.identity.selection_id
    with pytest.raises(FrozenInstanceError):
        selection.region_id = "changed"  # type: ignore[misc]


def test__selection__rejects_rendered_evidence_tampering() -> None:
    selection = OllamaMultimodalSelection.from_rendered_region(_region())

    with pytest.raises(ValueError, match="does not match rendered evidence"):
        replace(selection, png_sha256="0" * 64)
