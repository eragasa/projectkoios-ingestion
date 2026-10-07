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
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.proposal.source import (
    LayoutRegionProposalSource,
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
        source = LayoutRegionProposalSource.create(
            detector_name=f"layoutparser:{configuration.backend_name}",
            detector_version=(
                f"{configuration.package_version}/"
                f"{configuration.backend_version}"
            ),
            resource_identity=configuration.model_identity,
            resource_sha256=configuration.model_sha256,
            configuration_id=configuration.configuration_id,
            evidence=(
                ("backend", configuration.backend_name),
                ("package", "layoutparser"),
            ),
        )
        label_mapping = dict(configuration.label_mapping)
        proposals = tuple(
            LayoutRegionProposal.create(
                render_id=request.render.render_id,
                proposal_source_id=source.proposal_source_id,
                kind=label_mapping[detection.label],
                bounding_box_pixels=detection.bounding_box_pixels,
                confidence=detection.confidence,
                evidence=(
                    ("detection_id", detection.detection_id),
                    ("model_label", detection.label),
                ),
            )
            for detection in request.detections
        )
        return LayoutParserProposalResult.create(
            request=request,
            proposal_source=source,
            proposals=proposals,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
