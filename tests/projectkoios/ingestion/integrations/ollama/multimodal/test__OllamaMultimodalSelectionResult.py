from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalSelectionResult,
    OllamaMultimodalSelectionStatus,
)


def test__selection_result__owns_complete_selection_coverage() -> None:
    request = _request()
    processor, _ = _processor(request)
    result = processor.action(request=request).selection_results[0]

    assert isinstance(result, OllamaMultimodalSelectionResult)
    assert result.status is OllamaMultimodalSelectionStatus.PROPOSED
    assert result.selection_id == result.identity.selection_id


def test__selection_result__rejects_provenance_tampering() -> None:
    request = _request()
    processor, _ = _processor(request)
    result = processor.action(request=request).selection_results[0]

    with pytest.raises(ValueError, match="provenance identity mismatch"):
        replace(result, region_id="changed")
