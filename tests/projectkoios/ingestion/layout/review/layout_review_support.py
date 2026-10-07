"""Object fixture builder for layout-review contract tests."""

from __future__ import annotations

from projectkoios.ingestion.integrations.layout_parser.actionizer import (
    LayoutParserRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.layout_parser.configuration import (
    LayoutParserProposalConfiguration,
)
from projectkoios.ingestion.integrations.layout_parser.detection import (
    LayoutParserDetection,
)
from projectkoios.ingestion.integrations.layout_parser.request import (
    LayoutParserProposalRequest,
)
from projectkoios.ingestion.integrations.layout_parser.result import (
    LayoutParserProposalResult,
)
from projectkoios.ingestion.layout.contracts import (
    DeterministicLayoutProcessor,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.render.mapping import LayoutPixelMapping
from projectkoios.ingestion.layout.review.actionizer import (
    DeterministicLayoutReviewActionizer,
)
from projectkoios.ingestion.layout.review.configuration import (
    LayoutReviewConfiguration,
)
from projectkoios.ingestion.layout.review.limits.definition import (
    MAX_LAYOUT_REVIEW_COMPARISONS,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.layout.review.result import LayoutReviewCase
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedPage,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.pdf.models import PYMUPDF_COORDINATE_SYSTEM
from projectkoios.ingestion.sha256.hash import SHA256Hash


class LayoutReviewFixture:
    """Build related render, proposal, review, and annotation test inputs."""

    __slots__ = ()

    def source_page(self) -> tuple[SourceDocument, ExtractedPage]:
        """Create a two-block source page with simple exact geometry."""
        source = SourceDocument.from_bytes(
            b"layout review fixture",
            source_id="fixture:layout-review",
            media_type="application/pdf",
            locator="fixture://layout-review.pdf",
        )
        blocks = tuple(
            ExtractedBlock.create(
                kind="text",
                source_spans=(
                    SourceSpan(
                        source_id=source.source_id,
                        source_blob_id=source.blob_id,
                        page_index=0,
                        source_object_id=f"block:{ordinal}",
                        bounding_box=box,
                    ),
                ),
                extraction_method="fixture",
                confidence=1.0,
                text=f"block {ordinal}",
            )
            for ordinal, box in (
                (1, (10.0, 10.0, 40.0, 20.0)),
                (2, (10.0, 40.0, 40.0, 50.0)),
            )
        )
        page = ExtractedPage(
            page_index=0,
            width=100.0,
            height=100.0,
            blocks=blocks,
            coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
        )
        return source, page

    def render_evidence(
        self,
    ) -> tuple[SourceDocument, ExtractedPage, LayoutPageRenderEvidence]:
        """Create an exact unrotated two-pixels-per-point page render."""
        source, page = self.source_page()
        layout = DeterministicLayoutProcessor().analyze_page(source, page)
        mapping = LayoutPixelMapping.create(
            source_coordinate_system=layout.coordinate_system,
            requested_source_bounding_box=(0.0, 0.0, 100.0, 100.0),
            effective_source_bounding_box=(0.0, 0.0, 100.0, 100.0),
            pixel_to_source_matrix=(0.5, 0.0, 0.0, 0.5, 0.0, 0.0),
            pixel_rounding="fixture-exact",
            page_rotation_degrees=0,
            image_width=200,
            image_height=200,
        )
        render = LayoutPageRenderEvidence.create(
            source_id=layout.source_id,
            source_blob_id=layout.source_blob_id,
            page_index=layout.page_index,
            mapping=mapping,
            image_media_type="image/png",
            image_sha256="a" * 64,
            renderer_name="fixture-renderer",
            renderer_version="1",
            backend_name="fixture",
            backend_version="1",
            renderer_configuration_id="fixture-renderer:scale-2",
        )
        return source, page, render

    def layout_parser_configuration(
        self,
    ) -> LayoutParserProposalConfiguration:
        """Create the bounded five-label LayoutParser fixture configuration."""
        return LayoutParserProposalConfiguration(
            package_version="0.3.4",
            backend_name="effdet",
            backend_version="0.4.1",
            model_identity="layoutparser/efficientdet:PubLayNet/d0",
            model_sha256=SHA256Hash("b" * 64),
            label_mapping=(
                ("Figure", LayoutRegionKind.FIGURE),
                ("List", LayoutRegionKind.LIST),
                ("Table", LayoutRegionKind.TABLE),
                ("Text", LayoutRegionKind.TEXT),
                ("Title", LayoutRegionKind.TITLE),
            ),
        )

    def prepared_case(
        self,
    ) -> tuple[
        ExtractedPage,
        LayoutParserProposalResult,
        LayoutReviewRequest,
        LayoutReviewCase,
    ]:
        """Create adapter and review results for the shared two-block page."""
        source, page, render = self.render_evidence()
        detection = LayoutParserDetection.create(
            render_id=render.render_id,
            label="Text",
            bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
            confidence=0.95,
        )
        adapter_request = LayoutParserProposalRequest.create(
            render=render,
            detections=(detection,),
            configuration=self.layout_parser_configuration(),
        )
        adapter_result = LayoutParserRegionProposalActionizer().action(
            request=adapter_request
        )
        layout = DeterministicLayoutProcessor().analyze_page(source, page)
        review_request = LayoutReviewRequest.create(
            layout=layout,
            render=render,
            proposal_source=adapter_result.proposal_source,
            proposals=adapter_result.proposals,
            configuration=LayoutReviewConfiguration(
                minimum_block_intersection_ratio=0.5,
                minimum_page_coverage_ratio=0.9,
            ),
        )
        review_case = DeterministicLayoutReviewActionizer().action(
            request=review_request
        )
        return page, adapter_result, review_request, review_case

    def maximum_comparison_request(self) -> LayoutReviewRequest:
        """Create a request at the hard block-proposal comparison limit."""
        source = SourceDocument.from_bytes(
            b"layout maximum-comparison fixture",
            source_id="fixture:layout-review-maximum-comparisons",
            media_type="application/pdf",
            locator="fixture://layout-review-maximum-comparisons.pdf",
        )
        blocks = tuple(
            ExtractedBlock.create(
                kind="text",
                source_spans=(
                    SourceSpan(
                        source_id=source.source_id,
                        source_blob_id=source.blob_id,
                        page_index=0,
                        source_object_id=f"block:{index:03d}",
                        bounding_box=(
                            10.0 + (index % 10) * 20.0,
                            10.0 + (index // 10) * 20.0,
                            15.0 + (index % 10) * 20.0,
                            15.0 + (index // 10) * 20.0,
                        ),
                    ),
                ),
                extraction_method="fixture",
                confidence=1.0,
                text=f"bounded block {index}",
            )
            for index in range(100)
        )
        page = ExtractedPage(
            page_index=0,
            width=500.0,
            height=500.0,
            blocks=blocks,
            coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
        )
        layout = DeterministicLayoutProcessor().analyze_page(source, page)
        mapping = LayoutPixelMapping.create(
            source_coordinate_system=layout.coordinate_system,
            requested_source_bounding_box=(0.0, 0.0, 500.0, 500.0),
            effective_source_bounding_box=(0.0, 0.0, 500.0, 500.0),
            pixel_to_source_matrix=(0.5, 0.0, 0.0, 0.5, 0.0, 0.0),
            pixel_rounding="fixture-exact",
            page_rotation_degrees=0,
            image_width=1_000,
            image_height=1_000,
        )
        render = LayoutPageRenderEvidence.create(
            source_id=layout.source_id,
            source_blob_id=layout.source_blob_id,
            page_index=layout.page_index,
            mapping=mapping,
            image_media_type="image/png",
            image_sha256="f" * 64,
            renderer_name="fixture-renderer",
            renderer_version="1",
            backend_name="fixture",
            backend_version="1",
            renderer_configuration_id="fixture-renderer:max-comparisons",
        )
        detections = tuple(
            LayoutParserDetection.create(
                render_id=render.render_id,
                label="Text",
                bounding_box_pixels=(
                    600.0 + (index % 100) * 4.0,
                    600.0 + (index // 100) * 4.0,
                    602.0 + (index % 100) * 4.0,
                    602.0 + (index // 100) * 4.0,
                ),
                confidence=1.0,
            )
            for index in range(1_000)
        )
        proposal_result = LayoutParserRegionProposalActionizer().action(
            request=LayoutParserProposalRequest.create(
                render=render,
                detections=detections,
                configuration=self.layout_parser_configuration(),
            )
        )
        configuration = LayoutReviewConfiguration(
            max_blocks=len(layout.input_text_blocks),
            max_proposals=len(proposal_result.proposals),
            max_comparisons=MAX_LAYOUT_REVIEW_COMPARISONS,
            max_overlaps=1,
        )
        return LayoutReviewRequest.create(
            layout=layout,
            render=render,
            proposal_source=proposal_result.proposal_source,
            proposals=proposal_result.proposals,
            configuration=configuration,
        )
