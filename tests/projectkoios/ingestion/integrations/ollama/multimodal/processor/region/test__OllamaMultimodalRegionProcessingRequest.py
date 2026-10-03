from dataclasses import FrozenInstanceError, replace

import pytest
from conftest import _region, _request
from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalSelection,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.request import (  # noqa: E501
    OllamaMultimodalRegionProcessingRequest,
)


def test__region_processing_request__is_an_action_request() -> None:
    assert issubclass(
        OllamaMultimodalRegionProcessingRequest,
        DataObjectActionRequest,
    )


def test__region_processing_request__identity_covers_evidence() -> None:
    request = _request()
    assert request.request_id == (
        "ollama-multimodal-request:sha256:"
        "8da5283592cc446daa009cf34cb3dc87428f5a1b9dd1f25fe60a2e1702fe437b"
    )
    changed = OllamaMultimodalRegionProcessingRequest.create(
        (OllamaMultimodalSelection.from_rendered_region(_region(0, 9)),)
    )

    assert request.request_id != changed.request_id
    assert request.prompt.rendered_sha256 != changed.prompt.rendered_sha256
    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="identity"):
        replace(request, request_id="bad")
