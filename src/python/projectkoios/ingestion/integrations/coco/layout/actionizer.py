"""Pure adaptation of frozen COCO detections into layout proposals."""

from __future__ import annotations

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.configuration import (
    CocoLayoutProposalConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.request import (
    CocoLayoutProposalRequest,
)
from projectkoios.ingestion.integrations.coco.layout.result import (
    CocoLayoutProposalResult,
)


class CocoLayoutRegionProposalActionizer(
    ConfigurableDataObjectActionizer[
        CocoLayoutProposalConfiguration,
        CocoLayoutProposalRequest,
        CocoLayoutProposalResult,
    ]
):
    """Translate exact COCO box detections without running inference."""

    __slots__ = ()

    actionizer_name = CocoLayoutProposalResult.ACTIONIZER_NAME
    actionizer_version = CocoLayoutProposalResult.ACTIONIZER_VERSION
    configuration_type = CocoLayoutProposalConfiguration

    def action(
        self, *, request: CocoLayoutProposalRequest
    ) -> CocoLayoutProposalResult:
        """Adapt one immutable, completely validated COCO request."""
        if type(request) is not CocoLayoutProposalRequest:
            raise TypeError("request must be CocoLayoutProposalRequest")
        return CocoLayoutProposalResult(request=request)
