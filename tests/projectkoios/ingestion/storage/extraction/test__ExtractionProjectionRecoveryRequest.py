from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.storage.extraction.recovery.request import (
    ExtractionProjectionRecoveryRequest,
)


def test__extraction_projection_recovery_request__is_bounded() -> None:
    request = ExtractionProjectionRecoveryRequest.create(maximum_records=12)

    assert isinstance(request, DataObjectActionRequest)
    assert request.maximum_records == 12
