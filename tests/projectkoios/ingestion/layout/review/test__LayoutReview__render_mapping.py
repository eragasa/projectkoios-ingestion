from __future__ import annotations

from io import BytesIO

import pytest
from projectkoios.ingestion.integrations.layout_parser.actionizer import (
    LayoutParserRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.layout_parser.request import (
    LayoutParserProposalRequest,
)
from projectkoios.ingestion.layout.contracts import (
    DeterministicLayoutProcessor,
)
from projectkoios.ingestion.layout.limits.definition import (
    MAX_LAYOUT_IDENTITY_FIELD_CHARACTERS,
    MAX_LAYOUT_PAGE_INDEX,
)
from projectkoios.ingestion.layout.limits.error import LayoutLimitError
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.render.limits.definition import (
    MAX_LAYOUT_RENDER_DIMENSION_PIXELS,
    MAX_LAYOUT_RENDER_PIXELS,
)
from projectkoios.ingestion.layout.render.limits.error import (
    LayoutRenderLimitError,
)
from projectkoios.ingestion.layout.render.mapping import LayoutPixelMapping
from projectkoios.ingestion.layout.review.actionizer import (
    DeterministicLayoutReviewActionizer,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf.adapters.pymupdf.extraction import (
    PyMuPdfExtractor,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.pdf.models import (
    PYMUPDF_COORDINATE_SYSTEM,
    PageRegionSelection,
)

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)

FIXTURE = LayoutReviewFixture()


@pytest.mark.parametrize(
    (
        "rotation",
        "image_width",
        "image_height",
        "matrix",
        "expected_block_box",
    ),
    (
        # Unrotated raster: source axes retain direction at two pixels/point.
        (
            0,
            200,
            100,
            (0.5, 0.0, 0.0, 0.5, 0.0, 0.0),
            (20.0, 20.0, 80.0, 40.0),
        ),
        # Quarter-turn rows swap raster dimensions and exercise translation.
        (
            90,
            100,
            200,
            (0.0, -0.5, 0.5, 0.0, 0.0, 50.0),
            (60.0, 20.0, 80.0, 80.0),
        ),
        # A half turn reverses both axes around the source-page far corner.
        (
            180,
            200,
            100,
            (-0.5, 0.0, 0.0, -0.5, 100.0, 50.0),
            (120.0, 60.0, 180.0, 80.0),
        ),
        # The inverse quarter turn swaps axes with the opposite orientation.
        (
            270,
            100,
            200,
            (0.0, 0.5, -0.5, 0.0, 100.0, 0.0),
            (20.0, 120.0, 40.0, 180.0),
        ),
    ),
)
def test__layout_pixel_mapping__maps_every_quarter_turn(
    rotation: int,
    image_width: int,
    image_height: int,
    matrix: tuple[float, float, float, float, float, float],
    expected_block_box: tuple[float, float, float, float],
) -> None:
    mapping = LayoutPixelMapping.create(
        source_coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
        requested_source_bounding_box=(0.0, 0.0, 100.0, 50.0),
        effective_source_bounding_box=(0.0, 0.0, 100.0, 50.0),
        pixel_to_source_matrix=matrix,
        pixel_rounding="fixture-exact",
        page_rotation_degrees=rotation,
        image_width=image_width,
        image_height=image_height,
    )

    assert mapping.source_box_to_pixel_box(
        (10.0, 10.0, 40.0, 20.0)
    ) == expected_block_box


@pytest.mark.parametrize(
    ("matrix", "rotation", "message"),
    (
        # A zero determinant has no source-to-pixel inverse.
        ((1.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0, "invertible"),
        # A non-finite external coefficient is rejected before identity hashing.
        ((float("inf"), 0.0, 0.0, 1.0, 0.0, 0.0), 0, "finite"),
        # A shear must not masquerade as a supported unrotated render.
        ((1.0, 0.0, 0.25, 1.0, 0.0, 0.0), 0, "quarter turn"),
        # Rotation metadata must agree with the affine axis orientation.
        ((0.5, 0.0, 0.0, 0.5, 0.0, 0.0), 90, "quarter turn"),
    ),
)
def test__layout_pixel_mapping__rejects_unsupported_affine_geometry(
    matrix: tuple[float, float, float, float, float, float],
    rotation: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LayoutPixelMapping.create(
            source_coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            requested_source_bounding_box=(0.0, 0.0, 100.0, 100.0),
            effective_source_bounding_box=(0.0, 0.0, 100.0, 100.0),
            pixel_to_source_matrix=matrix,
            pixel_rounding="fixture-exact",
            page_rotation_degrees=rotation,
            image_width=100,
            image_height=100,
        )


def test__layout_pixel_mapping__rejects_inconsistent_effective_bounds() -> None:
    with pytest.raises(ValueError, match="effective source bounds"):
        LayoutPixelMapping.create(
            source_coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            requested_source_bounding_box=(0.0, 0.0, 100.0, 100.0),
            effective_source_bounding_box=(0.0, 0.0, 99.0, 100.0),
            pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            pixel_rounding="fixture-exact",
            page_rotation_degrees=0,
            image_width=100,
            image_height=100,
        )


@pytest.mark.parametrize(
    ("width", "height", "accepted"),
    (
        # The declared dimension boundary remains valid when area is small.
        (MAX_LAYOUT_RENDER_DIMENSION_PIXELS, 1, True),
        # One pixel beyond the dimension boundary is rejected before hashing.
        (MAX_LAYOUT_RENDER_DIMENSION_PIXELS + 1, 1, False),
        # The exact total-pixel boundary is valid.
        (5_000, MAX_LAYOUT_RENDER_PIXELS // 5_000, True),
        # The smallest adjacent rectangular case exceeds total-pixel policy.
        (5_001, MAX_LAYOUT_RENDER_PIXELS // 5_000, False),
    ),
)
def test__layout_pixel_mapping__enforces_render_boundaries(
    width: int,
    height: int,
    accepted: bool,
) -> None:
    try:
        mapping = LayoutPixelMapping.create(
            source_coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            requested_source_bounding_box=(
                0.0,
                0.0,
                float(width),
                float(height),
            ),
            effective_source_bounding_box=(
                0.0,
                0.0,
                float(width),
                float(height),
            ),
            pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            pixel_rounding="fixture-exact",
            page_rotation_degrees=0,
            image_width=width,
            image_height=height,
        )
    except LayoutRenderLimitError:
        assert not accepted
    else:
        assert accepted
        assert mapping.image_width == width


@pytest.mark.parametrize(
    ("offset", "dimension", "accepted"),
    (
        # Half-pixel outward rounding preserves complete full-page coverage.
        (-0.25, 201, True),
        # A two-pixel displacement cannot be attributed to outward rounding.
        (-1.0, 202, False),
    ),
)
def test__layout_review_request__bounds_translated_render_rounding(
    offset: float,
    dimension: int,
    accepted: bool,
) -> None:
    source, page = FIXTURE.source_page()
    layout = DeterministicLayoutProcessor().analyze_page(source, page)
    mapping = LayoutPixelMapping.create(
        source_coordinate_system=layout.coordinate_system,
        requested_source_bounding_box=(0.0, 0.0, 100.0, 100.0),
        effective_source_bounding_box=(
            offset,
            offset,
            offset + dimension * 0.5,
            offset + dimension * 0.5,
        ),
        pixel_to_source_matrix=(0.5, 0.0, 0.0, 0.5, offset, offset),
        pixel_rounding="fixture-outward",
        page_rotation_degrees=0,
        image_width=dimension,
        image_height=dimension,
    )
    render = LayoutPageRenderEvidence.create(
        source_id=layout.source_id,
        source_blob_id=layout.source_blob_id,
        page_index=layout.page_index,
        mapping=mapping,
        image_media_type="image/png",
        image_sha256="c" * 64,
        renderer_name="fixture-renderer",
        renderer_version="1",
        backend_name="fixture",
        backend_version="1",
        renderer_configuration_id="fixture-renderer:outward",
    )
    proposal_result = LayoutParserRegionProposalActionizer().action(
        request=LayoutParserProposalRequest.create(
            render=render,
            detections=(),
            configuration=FIXTURE.layout_parser_configuration(),
        )
    )
    if accepted:
        request = LayoutReviewRequest.create(
            layout=layout,
            render=render,
            proposal_source=proposal_result.proposal_source,
            proposals=proposal_result.proposals,
        )
        assert mapping.source_box_to_pixel_box(
            (0.0, 0.0, 10.0, 10.0)
        ) == (0.5, 0.5, 20.5, 20.5)
        assert request.render is render
    else:
        with pytest.raises(ValueError, match="outward pixel rounding"):
            LayoutReviewRequest.create(
                layout=layout,
                render=render,
                proposal_source=proposal_result.proposal_source,
                proposals=proposal_result.proposals,
            )


@pytest.mark.parametrize(
    ("rotation", "page_width", "page_height", "raw_cropbox", "dpi"),
    (
        # An ordinary quarter-turn page preserves exact rotated geometry.
        (90, 120, 200, None, 72),
        # A protruding crop box exercises real clipping and nontrivial scale.
        (270, 612, 1_224, "[0 381.6 612.1 1224.1]", 300),
    ),
)
def test__pymupdf_renderer__projects_exact_rotated_layout_evidence(
    rotation: int,
    page_width: int,
    page_height: int,
    raw_cropbox: str | None,
    dpi: int,
) -> None:
    pymupdf = pytest.importorskip("pymupdf")
    document = pymupdf.open()
    page = document.new_page(width=page_width, height=page_height)
    if raw_cropbox is not None:
        document.xref_set_key(page.xref, "CropBox", raw_cropbox)
    page.insert_text((20, 40), "rotated layout projection")
    page.set_rotation(rotation)
    payload = document.tobytes()
    document.close()
    source = SourceDocument.from_bytes(
        payload,
        source_id=f"fixture:rotated-layout-projection:{rotation}",
        media_type="application/pdf",
        locator="memory://rotated-layout-projection.pdf",
    )
    extracted_page = PyMuPdfExtractor(
        low_text_character_threshold=0
    ).extract(source, BytesIO(payload)).document.pages[0]
    layout = DeterministicLayoutProcessor().analyze_page(
        source, extracted_page
    )
    renderer = PyMuPdfRegionRenderer(resolution_dpi=dpi)
    rendered_region = renderer.render(
        source,
        BytesIO(payload),
        (PageRegionSelection.for_full_page(source, 0),),
    )[0]

    render = renderer.project_layout_render_evidence(
        rendered_region=rendered_region
    )

    assert render.mapping.requested_source_bounding_box == (
        rendered_region.source_bounding_box
    )
    assert render.mapping.effective_source_bounding_box == (
        rendered_region.effective_source_bounding_box
    )
    assert render.mapping.pixel_to_source_matrix == (
        rendered_region.pixel_to_source_matrix
    )
    assert render.mapping.page_rotation_degrees == rotation
    assert (render.image_width, render.image_height) == (
        rendered_region.width_pixels,
        rendered_region.height_pixels,
    )
    assert render.image_sha256 == rendered_region.content_sha256

    proposal_result = LayoutParserRegionProposalActionizer().action(
        request=LayoutParserProposalRequest.create(
            render=render,
            detections=(),
            configuration=FIXTURE.layout_parser_configuration(),
        )
    )
    request = LayoutReviewRequest.create(
        layout=layout,
        render=render,
        proposal_source=proposal_result.proposal_source,
        proposals=proposal_result.proposals,
    )
    case = DeterministicLayoutReviewActionizer().action(request=request)
    assert case.render_id == render.render_id
    assert all(
        review.mapping_id == render.mapping.mapping_id
        for review in case.block_reviews
    )

    cropped_region = renderer.render(
        source,
        BytesIO(payload),
        (
            PageRegionSelection.for_bounding_box(
                source,
                0,
                (
                    0.0,
                    0.0,
                    layout.page_width / 2.0,
                    layout.page_height / 2.0,
                ),
            ),
        ),
    )[0]
    with pytest.raises(ValueError, match="full-page"):
        renderer.project_layout_render_evidence(
            rendered_region=cropped_region
        )


@pytest.mark.parametrize(
    ("page_index", "accepted"),
    (
        # The exact page-index boundary remains serializable.
        (MAX_LAYOUT_PAGE_INDEX, True),
        # One page beyond policy is rejected before render hashing.
        (MAX_LAYOUT_PAGE_INDEX + 1, False),
    ),
)
def test__layout_render_evidence__bounds_page_index_before_hashing(
    page_index: int,
    accepted: bool,
) -> None:
    _, _, existing_render = FIXTURE.render_evidence()
    try:
        render = LayoutPageRenderEvidence.create(
            source_id=existing_render.source_id,
            source_blob_id=existing_render.source_blob_id,
            page_index=page_index,
            mapping=existing_render.mapping,
            image_media_type=existing_render.image_media_type,
            image_sha256=str(existing_render.image_sha256),
            renderer_name=existing_render.renderer_name,
            renderer_version=existing_render.renderer_version,
            backend_name=existing_render.backend_name,
            backend_version=existing_render.backend_version,
            renderer_configuration_id=(
                existing_render.renderer_configuration_id
            ),
        )
    except LayoutLimitError:
        assert not accepted
    else:
        assert accepted
        assert render.page_index == page_index


@pytest.mark.parametrize(
    ("rounding_length", "accepted"),
    (
        # The exact shared identity-field boundary is accepted.
        (MAX_LAYOUT_IDENTITY_FIELD_CHARACTERS, True),
        # One additional character is rejected before mapping hashing.
        (MAX_LAYOUT_IDENTITY_FIELD_CHARACTERS + 1, False),
    ),
)
def test__layout_pixel_mapping__bounds_identity_text_before_hashing(
    rounding_length: int,
    accepted: bool,
) -> None:
    rounding = "r" * rounding_length
    if accepted:
        mapping = LayoutPixelMapping.create(
            source_coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            requested_source_bounding_box=(0.0, 0.0, 1.0, 1.0),
            effective_source_bounding_box=(0.0, 0.0, 1.0, 1.0),
            pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            pixel_rounding=rounding,
            page_rotation_degrees=0,
            image_width=1,
            image_height=1,
        )
        assert mapping.pixel_rounding == rounding
    else:
        with pytest.raises(LayoutLimitError):
            LayoutPixelMapping.create(
                source_coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
                requested_source_bounding_box=(0.0, 0.0, 1.0, 1.0),
                effective_source_bounding_box=(0.0, 0.0, 1.0, 1.0),
                pixel_to_source_matrix=(
                    1.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                ),
                pixel_rounding=rounding,
                page_rotation_degrees=0,
                image_width=1,
                image_height=1,
            )
