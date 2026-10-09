"""Normalize frozen local detector observations into COCO profile evidence."""

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)

from .configuration import CocoLayoutDetectorConfiguration
from .request import CocoLayoutDetectorRequest
from .result import CocoLayoutDetectorResult


class CocoLayoutDetectorObservationActionizer(
    ConfigurableDataObjectActionizer[
        CocoLayoutDetectorConfiguration,
        CocoLayoutDetectorRequest,
        CocoLayoutDetectorResult,
    ]
):
    """Adapt local detector output without owning inference or model bytes."""

    __slots__ = ()

    actionizer_name = "coco-layout-detector-observation-adapter"
    actionizer_version = "1"
    configuration_type = CocoLayoutDetectorConfiguration

    def action(
        self, *, request: CocoLayoutDetectorRequest
    ) -> CocoLayoutDetectorResult:
        """Return deterministic accepted detections and limitations."""
        if type(request) is not CocoLayoutDetectorRequest:
            raise TypeError("request must be CocoLayoutDetectorRequest")
        return CocoLayoutDetectorResult.create(
            request=request,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
