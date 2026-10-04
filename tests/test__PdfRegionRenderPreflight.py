from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    PageRegionRenderer,
    PageRegionSelection,
    PdfRegionRenderer,
    PdfRegionRenderLimitError,
    RegionColorMode,
    RegionRenderConfiguration,
    SourceDocument,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.pdf.preflight import (
    PdfRegionRenderPreflight,
    PdfRegionRenderPreflightPlan,
)


def _source(
    payload: bytes = b"pdf fixture",
    *,
    media_type: str = "application/pdf",
    source_id: str = "fixture:preflight",
) -> SourceDocument:
    return SourceDocument.from_bytes(
        payload,
        source_id=source_id,
        media_type=media_type,
        locator="memory://preflight-fixture.pdf",
    )


def _policy(**changes: object) -> PdfRegionRenderPreflight:
    return PdfRegionRenderPreflight(RegionRenderConfiguration(**changes))


def test__preflight_plan__is_immutable_and_intrinsically_consistent() -> None:
    selection = PageRegionSelection.for_full_page(_source(), 0)
    plan = PdfRegionRenderPreflightPlan(
        selection=selection,
        width_pixels=10,
        height_pixels=20,
        channel_count=3,
        pixel_count=200,
        raster_byte_count=600,
    )

    assert plan.pixel_count == 200
    assert plan.raster_byte_count == 600
    with pytest.raises(FrozenInstanceError):
        plan.width_pixels = 11  # type: ignore[misc]
    with pytest.raises(ValueError, match="pixel_count"):
        replace(plan, pixel_count=199)
    with pytest.raises(ValueError, match="raster_byte_count"):
        replace(plan, raster_byte_count=599)
    for field in ("width_pixels", "height_pixels", "channel_count"):
        with pytest.raises(ValueError, match=field):
            replace(plan, **{field: 0})


def test__preflight__bounds_and_validates_the_request() -> None:
    source = _source()
    selection = PageRegionSelection.for_full_page(source, 0)
    policy = _policy(max_selections=2)
    consumed = 0

    def selections():
        nonlocal consumed
        while True:
            consumed += 1
            if consumed > 3:
                raise AssertionError("consumed beyond max_selections plus one")
            yield selection

    with pytest.raises(PdfRegionRenderLimitError, match="max_selections"):
        policy.prepare_request(source, selections())
    assert consumed == 3

    requested = policy.prepare_request(source, (selection, selection))
    assert requested == (selection, selection)
    assert policy.unique_selections(requested) == (selection,)

    with pytest.raises(ValueError, match="at least one"):
        policy.prepare_request(source, ())
    with pytest.raises(ValueError, match="application/pdf"):
        policy.prepare_request(
            _source(media_type="text/plain"),
            (selection,),
        )
    with pytest.raises(TypeError, match="PageRegionSelection"):
        policy.prepare_request(source, (object(),))  # type: ignore[arg-type]
    other_selection = PageRegionSelection.for_full_page(
        _source(source_id="fixture:other"), 0
    )
    with pytest.raises(ValueError, match="exact source"):
        policy.prepare_request(source, (other_selection,))


def test__preflight__validates_source_page_and_box_primitives() -> None:
    payload = b"exact pdf fixture"
    source = _source(payload)
    selection = PageRegionSelection.for_bounding_box(
        source, 1, (1.0, 2.0, 10.0, 20.0)
    )
    policy = _policy()

    policy.validate_source(source, payload)
    policy.validate_page_indices((selection,), 2)
    policy.validate_page_dimensions(10.0, 20.0)
    policy.validate_bounding_box(selection.bounding_box, 10.0, 20.0)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="do not agree"):
        policy.validate_source(source, payload + b"changed")
    with pytest.raises(ValueError, match="outside the PDF"):
        policy.validate_page_indices((selection,), 1)
    for dimensions in ((0.0, 1.0), (1.0, -1.0), (float("nan"), 1.0)):
        with pytest.raises(ValueError, match="positive area"):
            policy.validate_page_dimensions(*dimensions)
    with pytest.raises(ValueError, match="outside the page crop box"):
        policy.validate_bounding_box(
            selection.bounding_box,  # type: ignore[arg-type]
            9.0,
            20.0,
        )


def test__preflight__owns_scale_and_per_selection_resource_limits() -> None:
    source = _source()
    selection = PageRegionSelection.for_full_page(source, 0)
    policy = _policy(
        resolution_dpi=144,
        max_dimension_pixels=1_000,
        max_pixels=100_000,
        max_raster_bytes=300_000,
    )

    assert policy.validate_raster_scale(500.0, input_units_per_inch=72.0) == 2.0
    plan = policy.plan(selection, width_pixels=200, height_pixels=300)
    assert plan == PdfRegionRenderPreflightPlan(
        selection=selection,
        width_pixels=200,
        height_pixels=300,
        channel_count=3,
        pixel_count=60_000,
        raster_byte_count=180_000,
    )

    with pytest.raises(PdfRegionRenderLimitError, match="before raster"):
        policy.validate_raster_scale(501.0, input_units_per_inch=72.0)
    with pytest.raises(ValueError, match="finite display area"):
        policy.validate_raster_scale(float("inf"), input_units_per_inch=72.0)
    with pytest.raises(ValueError, match="input_units_per_inch"):
        policy.validate_raster_scale(1.0, input_units_per_inch=0.0)
    with pytest.raises(PdfRegionRenderLimitError, match="max_dimension_pixels"):
        policy.plan(selection, width_pixels=1_001, height_pixels=1)
    with pytest.raises(PdfRegionRenderLimitError, match="max_pixels"):
        policy.plan(selection, width_pixels=400, height_pixels=300)
    with pytest.raises(PdfRegionRenderLimitError, match="max_raster_bytes"):
        _policy(
            max_pixels=100_000,
            max_raster_bytes=100_000,
        ).plan(selection, width_pixels=200, height_pixels=200)

    grayscale = _policy(color_mode=RegionColorMode.GRAYSCALE).plan(
        selection, width_pixels=200, height_pixels=200
    )
    assert grayscale.channel_count == 1
    assert grayscale.raster_byte_count == grayscale.pixel_count


def test__preflight__owns_aggregate_unique_allocation_limits() -> None:
    source = _source()
    policy = _policy(
        max_pixels=60_000,
        max_raster_bytes=180_000,
        max_total_pixels=100_000,
        max_total_raster_bytes=300_000,
    )
    plans = tuple(
        policy.plan(
            PageRegionSelection.for_full_page(source, page_index),
            width_pixels=300,
            height_pixels=200,
        )
        for page_index in range(2)
    )

    with pytest.raises(PdfRegionRenderLimitError, match="max_total_pixels"):
        policy.validate_aggregate(plans)
    with pytest.raises(
        PdfRegionRenderLimitError, match="max_total_raster_bytes"
    ):
        _policy(
            max_pixels=60_000,
            max_raster_bytes=180_000,
            max_total_pixels=120_000,
            max_total_raster_bytes=300_000,
        ).validate_aggregate(plans)


def test__renderer_contract__has_canonical_nominal_public_bases() -> None:
    from projectkoios.ingestion.pdf import (
        PageRegionRenderer as PdfPackagePageRegionRenderer,
    )
    from projectkoios.ingestion.pdf import (
        PdfRegionRenderer as PdfPackageRegionRenderer,
    )

    assert PdfPackagePageRegionRenderer is PageRegionRenderer
    assert PdfPackageRegionRenderer is PdfRegionRenderer
    assert inspect.isabstract(PageRegionRenderer)
    assert inspect.isabstract(PdfRegionRenderer)
    assert issubclass(PdfRegionRenderer, PageRegionRenderer)
    assert issubclass(PyMuPdfRegionRenderer, PdfRegionRenderer)

    renderer: PageRegionRenderer = PyMuPdfRegionRenderer()
    assert renderer.name == "pymupdf-region-renderer"


def test__neutral_renderer_and_preflight_have_no_backend_references() -> None:
    package = (
        Path(__file__).parents[1]
        / "src"
        / "python"
        / "projectkoios"
        / "ingestion"
        / "pdf"
    )
    paths = [
        package / "renderer.py",
        *sorted((package / "preflight").glob("*.py")),
    ]
    forbidden_names = {
        "Document",
        "Matrix",
        "Page",
        "Pixmap",
        "Rect",
        "colorspace",
        "get_pixmap",
        "open",
        "tobytes",
    }

    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name.casefold()
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            (node.module or "").casefold()
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        }
        attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }

        assert all("pymupdf" not in module for module in imported_modules)
        assert "pymupdf" not in source.casefold()
        assert "Any" not in names
        assert forbidden_names.isdisjoint(names | attributes)
