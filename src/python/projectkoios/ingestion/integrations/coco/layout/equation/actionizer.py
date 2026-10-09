"""Pure actionizer for admitted COCO formula projection."""

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)

from .configuration import CocoLayoutEquationProjectionConfiguration
from .request import CocoLayoutEquationProjectionRequest
from .result import CocoLayoutEquationProjectionResult


class CocoLayoutEquationProjectionActionizer(
    ConfigurableDataObjectActionizer[
        CocoLayoutEquationProjectionConfiguration,
        CocoLayoutEquationProjectionRequest,
        CocoLayoutEquationProjectionResult,
    ]
):
    """Project admitted formula proposals without retrieval or recognition."""

    __slots__ = ()

    actionizer_name = "coco-layout-equation-projector"
    actionizer_version = "1"
    configuration_type = CocoLayoutEquationProjectionConfiguration

    def action(
        self, *, request: CocoLayoutEquationProjectionRequest
    ) -> CocoLayoutEquationProjectionResult:
        """Return deterministic candidates and explicit exclusions."""
        if type(request) is not CocoLayoutEquationProjectionRequest:
            raise TypeError(
                "request must be CocoLayoutEquationProjectionRequest"
            )
        return CocoLayoutEquationProjectionResult.create(
            request=request,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
