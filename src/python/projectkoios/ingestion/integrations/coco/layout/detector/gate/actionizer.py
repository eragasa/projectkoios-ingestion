"""Deterministic local-detector admission gate."""

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)

from .configuration import CocoLayoutDetectorGateConfiguration
from .request import CocoLayoutDetectorGateRequest
from .result import CocoLayoutDetectorGateResult


class CocoLayoutDetectorGateActionizer(
    ConfigurableDataObjectActionizer[
        CocoLayoutDetectorGateConfiguration,
        CocoLayoutDetectorGateRequest,
        CocoLayoutDetectorGateResult,
    ]
):
    """Fail closed before detector evidence enters layout finalization."""

    __slots__ = ()

    actionizer_name = "coco-layout-detector-gate"
    actionizer_version = "1"
    configuration_type = CocoLayoutDetectorGateConfiguration

    def action(
        self, *, request: CocoLayoutDetectorGateRequest
    ) -> CocoLayoutDetectorGateResult:
        """Return deterministic finalization admission or escalation."""
        if type(request) is not CocoLayoutDetectorGateRequest:
            raise TypeError("request must be CocoLayoutDetectorGateRequest")
        return CocoLayoutDetectorGateResult.create(request=request)
