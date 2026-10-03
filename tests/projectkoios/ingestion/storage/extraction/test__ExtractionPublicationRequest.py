from __future__ import annotations

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.models import ExtractionResult
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)


def test__extraction_publication_request__binds_exact_extraction(
    extraction_result: ExtractionResult,
) -> None:
    request = ExtractionPublicationRequest.create(
        extraction=extraction_result,
    )

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(request, AbstractImmutableDataObject)
    assert request.extraction is extraction_result
    assert request.request_id.startswith(
        "extraction-publication-request:sha256:"
    )
