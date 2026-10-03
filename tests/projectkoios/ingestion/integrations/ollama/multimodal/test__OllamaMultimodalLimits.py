from __future__ import annotations

import pytest
from projectkoios.ingestion.integrations.ollama.base import (
    OllamaMultimodalConfigurationError,
)
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalLimits,
)


def test__limits__reject_nonpositive_and_inconsistent_bounds() -> None:
    with pytest.raises(OllamaMultimodalConfigurationError):
        OllamaMultimodalLimits(max_selections=0)
    with pytest.raises(OllamaMultimodalConfigurationError):
        OllamaMultimodalLimits(
            max_image_bytes=2,
            max_total_image_bytes=1,
        )
