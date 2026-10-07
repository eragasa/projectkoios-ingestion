"""Adapt frozen LayoutParser detections into domain proposals."""

from __future__ import annotations

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.integrations.layout_parser.configuration import (
    LayoutParserProposalConfiguration,
)
from projectkoios.ingestion.integrations.layout_parser.request import (
    LayoutParserProposalRequest,
)
from projectkoios.ingestion.integrations.layout_parser.result import (
    LayoutParserProposalResult,
)


class LayoutParserRegionProposalActionizer(
    ConfigurableDataObjectActionizer[
        LayoutParserProposalConfiguration,
        LayoutParserProposalRequest,
        LayoutParserProposalResult,
    ]
):
    """Translate exact external detections without running vendor inference."""

    __slots__ = ()

    actionizer_name = "layout-parser-region-proposal-adapter"
    actionizer_version = "1"
    configuration_type = LayoutParserProposalConfiguration

    def action(
        self, *, request: LayoutParserProposalRequest
    ) -> LayoutParserProposalResult:
        """Adapt one complete immutable detection request."""
        if type(request) is not LayoutParserProposalRequest:
            raise TypeError("request must be LayoutParserProposalRequest")
        configuration = request.configuration
        if type(configuration) is not LayoutParserProposalConfiguration:
            raise TypeError("action configuration contract differs")
        return LayoutParserProposalResult.create(
            request=request,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
