from conftest import _processor, _region, _request
from projectkoios.ingestion.integrations.ollama.base import OllamaRequestOptions
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalSelection,
    build_ollama_multimodal_cache_key,
)
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.request import (  # noqa: E501
    OllamaMultimodalRegionProcessingRequest,
)


def test__cache_key__covers_request_and_processor_identity() -> None:
    request = _request()
    changed_request = OllamaMultimodalRegionProcessingRequest.create(
        (OllamaMultimodalSelection.from_rendered_region(_region(0, 9)),)
    )
    processor, _ = _processor(request)
    changed_model, _ = _processor(request, digest="b" * 64)
    changed_options, _ = _processor(
        request,
        options=OllamaRequestOptions(seed=1),
    )

    key = build_ollama_multimodal_cache_key(request, processor.identity())
    assert key != build_ollama_multimodal_cache_key(
        changed_request,
        processor.identity(),
    )
    assert key != build_ollama_multimodal_cache_key(
        request,
        changed_model.identity(),
    )
    assert key != build_ollama_multimodal_cache_key(
        request,
        changed_options.identity(),
    )
