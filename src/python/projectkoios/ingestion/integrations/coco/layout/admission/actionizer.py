"""Pure actionizer for generic per-category COCO region admission."""

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)

from .configuration import CocoLayoutRegionAdmissionConfiguration
from .request import CocoLayoutRegionAdmissionRequest
from .result import CocoLayoutRegionAdmissionResult


class CocoLayoutRegionAdmissionActionizer(
    ConfigurableDataObjectActionizer[
        CocoLayoutRegionAdmissionConfiguration,
        CocoLayoutRegionAdmissionRequest,
        CocoLayoutRegionAdmissionResult,
    ]
):
    """Admit supported COCO regions without granting page authority."""

    __slots__ = ()

    actionizer_name = "coco-layout-region-admission"
    actionizer_version = "1"
    configuration_type = CocoLayoutRegionAdmissionConfiguration

    def action(
        self, *, request: CocoLayoutRegionAdmissionRequest
    ) -> CocoLayoutRegionAdmissionResult:
        """Return complete independent outcomes for every profile category."""
        if type(request) is not CocoLayoutRegionAdmissionRequest:
            raise TypeError("request must be a region admission request")
        return CocoLayoutRegionAdmissionResult.create(
            request=request,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
