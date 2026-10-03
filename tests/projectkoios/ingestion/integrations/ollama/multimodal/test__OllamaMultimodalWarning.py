from __future__ import annotations

import pytest
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalWarning,
)


def test__warning__validates_its_own_bounded_fields() -> None:
    warning = OllamaMultimodalWarning(code="ollama.warning", message="unclear")

    assert warning.code == "ollama.warning"
    with pytest.raises(ValueError, match="controls"):
        OllamaMultimodalWarning(code="ollama.warning", message="bad\u0000")
