"""Complete immutable request for layout review case preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.contracts import PageLayoutResult
from projectkoios.ingestion.layout.proposal.region import LayoutRegionProposal
from projectkoios.ingestion.layout.proposal.source import (
    LayoutRegionProposalSource,
)
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.review.configuration import (
    LayoutReviewConfiguration,
)
from projectkoios.ingestion.layout.review.limits.error import (
    LayoutReviewLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutReviewRequest(
    ConfigurableDataObjectActionRequest[LayoutReviewConfiguration]
):
    """Bind baseline, pixels, proposals, source, and review bounds."""

    CONTRACT_NAME: ClassVar[str] = "layout-review-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    layout: PageLayoutResult
    render: LayoutPageRenderEvidence
    proposal_source: LayoutRegionProposalSource
    proposals: tuple[LayoutRegionProposal, ...]
    configuration: LayoutReviewConfiguration
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        layout: PageLayoutResult,
        render: LayoutPageRenderEvidence,
        proposal_source: LayoutRegionProposalSource,
        proposals: tuple[LayoutRegionProposal, ...],
        configuration: LayoutReviewConfiguration | None = None,
    ) -> LayoutReviewRequest:
        """Create one complete request after checking evidence consistency."""
        actual_configuration = configuration or LayoutReviewConfiguration()
        cls.validate(
            layout=layout,
            render=render,
            proposal_source=proposal_source,
            proposals=proposals,
            configuration=actual_configuration,
        )
        request_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            layout.result_id,
            render.render_id,
            proposal_source.proposal_source_id,
            tuple(proposal.proposal_id for proposal in proposals),
            actual_configuration.configuration_id,
        )
        return cls(
            request_id=request_id,
            layout=layout,
            render=render,
            proposal_source=proposal_source,
            proposals=proposals,
            configuration=actual_configuration,
        )

    @classmethod
    def validate(
        cls,
        *,
        layout: PageLayoutResult,
        render: LayoutPageRenderEvidence,
        proposal_source: LayoutRegionProposalSource,
        proposals: tuple[LayoutRegionProposal, ...],
        configuration: LayoutReviewConfiguration,
    ) -> None:
        """Reject stale identities, invalid bounds, and excessive inputs."""
        if type(layout) is not PageLayoutResult:
            raise TypeError("layout must be PageLayoutResult")
        if type(render) is not LayoutPageRenderEvidence:
            raise TypeError("render must be LayoutPageRenderEvidence")
        if type(proposal_source) is not LayoutRegionProposalSource:
            raise TypeError(
                "proposal_source must be LayoutRegionProposalSource"
            )
        if type(configuration) is not LayoutReviewConfiguration:
            raise TypeError("configuration must be LayoutReviewConfiguration")
        if not isinstance(proposals, tuple):
            raise TypeError("proposals must be a tuple")
        if len(layout.input_text_blocks) > configuration.max_blocks:
            raise LayoutReviewLimitError("layout text blocks exceed max_blocks")
        if len(proposals) > configuration.max_proposals:
            raise LayoutReviewLimitError("proposals exceed max_proposals")
        if (
            len(layout.input_text_blocks) * len(proposals)
            > configuration.max_comparisons
        ):
            raise LayoutReviewLimitError(
                "block-proposal comparisons exceed max_comparisons"
            )
        if (
            render.source_id != layout.source_id
            or render.source_blob_id != layout.source_blob_id
            or render.page_index != layout.page_index
            or render.mapping.source_coordinate_system
            != layout.coordinate_system
            or render.mapping.page_rotation_degrees != layout.rotation_degrees
        ):
            raise ValueError("render does not identify the layout source page")
        expected_page_box = LayoutValueValidation.require_box(
            "layout_page_bounding_box",
            (0.0, 0.0, layout.page_width, layout.page_height),
        )
        if render.mapping.requested_source_bounding_box != expected_page_box:
            raise ValueError("layout review requires an exact full-page render")
        requested = render.mapping.requested_source_bounding_box
        effective = render.mapping.effective_source_bounding_box
        a, b, c, d, _, _ = render.mapping.pixel_to_source_matrix
        x_rounding = abs(a) + abs(c)
        y_rounding = abs(b) + abs(d)
        tolerance = 1e-9
        if (
            abs(effective[0] - requested[0]) > x_rounding + tolerance
            or abs(effective[1] - requested[1]) > y_rounding + tolerance
            or abs(effective[2] - requested[2]) > x_rounding + tolerance
            or abs(effective[3] - requested[3]) > y_rounding + tolerance
        ):
            raise ValueError(
                "effective render bounds exceed outward pixel rounding"
            )
        proposal_ids: set[str] = set()
        for proposal in proposals:
            if type(proposal) is not LayoutRegionProposal:
                raise TypeError("proposals must contain LayoutRegionProposal")
            if proposal.proposal_id in proposal_ids:
                raise ValueError("proposal IDs must be unique")
            proposal_ids.add(proposal.proposal_id)
            if proposal.render_id != render.render_id:
                raise ValueError("proposal does not identify the render")
            if (
                proposal.proposal_source_id
                != proposal_source.proposal_source_id
            ):
                raise ValueError("proposal source identity differs")
            x1, y1, x2, y2 = proposal.bounding_box_pixels
            if (
                x1 < 0.0
                or y1 < 0.0
                or x2 > render.image_width
                or y2 > render.image_height
            ):
                raise ValueError("proposal bounding box exceeds render bounds")

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout review request contract")
        self.validate(
            layout=self.layout,
            render=self.render,
            proposal_source=self.proposal_source,
            proposals=self.proposals,
            configuration=self.configuration,
        )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.layout.result_id,
            self.render.render_id,
            self.proposal_source.proposal_source_id,
            tuple(proposal.proposal_id for proposal in self.proposals),
            self.configuration.configuration_id,
        )
        if self.request_id != expected:
            raise ValueError("layout review request ID is inconsistent")
