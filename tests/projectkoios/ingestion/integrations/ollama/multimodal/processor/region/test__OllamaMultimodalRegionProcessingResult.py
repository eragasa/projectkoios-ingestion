from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.result import (  # noqa: E501
    OllamaMultimodalRegionProcessingResult,
)


def test__region_processing_result__is_an_action_result() -> None:
    assert issubclass(
        OllamaMultimodalRegionProcessingResult,
        DataObjectActionResult,
    )


def test__region_processing_result__preserves_versioned_identity() -> None:
    request = _request()
    processor, _ = _processor(request)
    result = processor.action(request=request)

    assert result.contract_version == result.CONTRACT_VERSION == "1.0"
    assert result.result_id == (
        "ollama-multimodal-result:sha256:"
        "c3928ebd63bc2535f56a2910c25fe1128075e47e576d51e86f95e1d21a4ccd60"
    )


def test__region_processing_result__rejects_tampering() -> None:
    request = _request(2)
    processor, _ = _processor(request)
    result = processor.action(request=request)

    with pytest.raises(ValueError, match="coverage"):
        replace(
            result,
            selection_results=tuple(reversed(result.selection_results)),
        )
    with pytest.raises(ValueError, match="request identity"):
        replace(
            result,
            request_id="ollama-multimodal-request:sha256:" + "0" * 64,
        )
    with pytest.raises(ValueError, match="cacheable"):
        replace(result, cacheable=False)
