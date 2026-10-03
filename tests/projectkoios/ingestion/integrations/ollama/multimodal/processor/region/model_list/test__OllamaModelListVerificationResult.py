from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMetadataStage,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.model_list import (  # noqa: E501
    result as model_list_result,
)

OllamaModelListVerificationResult = (
    model_list_result.OllamaModelListVerificationResult
)


def test__model_list_result__is_a_versioned_action_result() -> None:
    request = _request()
    processor, _ = _processor(request)
    result = processor._verify_tags(OllamaMetadataStage.PREFLIGHT_TAGS)

    assert isinstance(result, DataObjectActionResult)
    assert result.CONTRACT_NAME == "ollama-model-list-verification-result"
    assert result.CONTRACT_VERSION == "1.0"
    assert result.failure is None


def test__model_list_result__rejects_non_tag_response() -> None:
    request = _request()
    processor, _ = _processor(request)
    preflight = processor._verify_preflight()
    result = OllamaModelListVerificationResult(
        failure=None,
        response_identity=preflight.metadata_responses[1],
    )

    with pytest.raises(ValueError, match="requires a tag response"):
        replace(
            result,
            response_identity=preflight.metadata_responses[0],
        )
