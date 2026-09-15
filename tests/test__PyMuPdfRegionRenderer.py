from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError, replace
from io import BytesIO

import pytest
from projectkoios.ingestion import (
    PYMUPDF_COORDINATE_SYSTEM,
    PageRegionSelection,
    PdfRegionRenderLimitError,
    PyMuPdfRegionRenderer,
    RegionColorMode,
    SourceDocument,
)

pymupdf = pytest.importorskip("pymupdf")


def _fixture_pdf() -> bytes:
    document = pymupdf.open()
    first = document.new_page(width=300, height=200)
    first.draw_rect((0, 0, 150, 200), color=(1, 0, 0), fill=(1, 0, 0))
    first.draw_rect((150, 0, 300, 200), color=(0, 0, 1), fill=(0, 0, 1))
    document.new_page(width=300, height=200).insert_text(
        (30, 80), "UNSELECTED PAGE"
    )
    third = document.new_page(width=400, height=500)
    third.set_cropbox(pymupdf.Rect(50, 100, 250, 400))
    third.draw_rect((10, 20, 110, 70), color=(0, 1, 0), fill=(0, 1, 0))
    third.set_rotation(90)
    document.set_page_labels(
        [{"startpage": 0, "prefix": "App-", "style": "D", "firstpagenum": 7}]
    )
    payload = document.tobytes()
    document.close()
    return payload


def _source(
    payload: bytes, locator: str = "memory://fixture.pdf"
) -> SourceDocument:
    return SourceDocument.from_bytes(
        payload,
        source_id="article:region-fixture",
        media_type="application/pdf",
        locator=locator,
    )


def test__page_region_selection__requires_explicit_valid_geometry() -> None:
    payload = _fixture_pdf()
    source = _source(payload)

    full_page = PageRegionSelection.for_full_page(source, 0)
    region = PageRegionSelection.for_bounding_box(source, 0, (0, 0, 300, 200))

    assert full_page.full_page is True
    assert full_page.bounding_box is None
    assert region.full_page is False
    assert region.bounding_box == (0.0, 0.0, 300.0, 200.0)
    assert region.coordinate_system == PYMUPDF_COORDINATE_SYSTEM
    with pytest.raises(FrozenInstanceError):
        region.page_index = 1  # type: ignore[misc]

    invalid_boxes = (
        (float("nan"), 0, 1, 1),
        (0, float("inf"), 1, 1),
        (0, 0, 10**400, 1),
        (-1, 0, 1, 1),
        (1, 0, 0, 1),
        (0, 1, 1, 1),
    )
    for bounding_box in invalid_boxes:
        with pytest.raises(ValueError):
            PageRegionSelection.for_bounding_box(
                source,
                0,
                bounding_box,
            )

    with pytest.raises(ValueError, match="full-page"):
        PageRegionSelection(
            source.source_id,
            source.blob_id,
            0,
            True,
            (0, 0, 1, 1),
        )
    with pytest.raises(ValueError, match="full_page=True"):
        PageRegionSelection(
            source.source_id,
            source.blob_id,
            0,
            False,
            None,
        )


def test__selection__canonicalizes_signed_zero_for_stable_identity() -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    positive = PageRegionSelection.for_bounding_box(
        source, 0, (0.0, 0.0, 1.0, 1.0)
    )
    negative = PageRegionSelection.for_bounding_box(
        source, 0, (-0.0, -0.0, 1.0, 1.0)
    )
    renderer = PyMuPdfRegionRenderer(resolution_dpi=72)

    positive_result = renderer.render(source, BytesIO(payload), (positive,))[0]
    negative_result = renderer.render(source, BytesIO(payload), (negative,))[0]
    combined = renderer.render(source, BytesIO(payload), (negative, positive))
    reversed_results = renderer.render(
        source, BytesIO(payload), (positive, negative)
    )

    assert (
        positive.bounding_box
        == negative.bounding_box
        == (
            0.0,
            0.0,
            1.0,
            1.0,
        )
    )
    assert positive_result.region_id == negative_result.region_id
    assert {result.region_id for result in combined} == {
        positive_result.region_id
    }
    assert {result.region_id for result in reversed_results} == {
        positive_result.region_id
    }
    assert all(
        result.source_bounding_box == (0.0, 0.0, 1.0, 1.0)
        for result in combined + reversed_results
    )


def test__renderer__renders_only_requested_regions_in_requested_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    right = PageRegionSelection.for_bounding_box(source, 0, (150, 0, 300, 200))
    rotated = PageRegionSelection.for_bounding_box(source, 2, (10, 20, 110, 70))
    calls: list[int] = []
    original = pymupdf.Page.get_pixmap

    def record_render(page: object, *args: object, **kwargs: object) -> object:
        calls.append(page.number)  # type: ignore[attr-defined]
        return original(page, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", record_render)

    results = PyMuPdfRegionRenderer(resolution_dpi=72).render(
        source,
        BytesIO(payload),
        (rotated, right, rotated),
    )

    assert calls == [2, 0]
    assert [result.page_index for result in results] == [2, 0, 2]
    assert results[0] is results[2]
    assert results[0].source_bounding_box == (10.0, 20.0, 110.0, 70.0)
    assert (results[0].width_pixels, results[0].height_pixels) == (50, 100)
    assert results[0].printed_page_label == "App-9"
    rotated_crop = pymupdf.Pixmap(results[0].content)
    rotated_center = (rotated_crop.height // 2) * rotated_crop.stride + (
        rotated_crop.width // 2
    ) * rotated_crop.n
    assert tuple(rotated_crop.samples[rotated_center : rotated_center + 3]) == (
        0,
        255,
        0,
    )
    assert results[1].source_bounding_box == (150.0, 0.0, 300.0, 200.0)
    assert results[1].content.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(results[1].content).hexdigest() == (
        results[1].content_sha256
    )
    blue_crop = pymupdf.Pixmap(results[1].content)
    center = (blue_crop.height // 2) * blue_crop.stride + (
        blue_crop.width // 2
    ) * blue_crop.n
    assert tuple(blue_crop.samples[center : center + 3]) == (0, 0, 255)


def test__renderer__full_page_is_explicit_and_uses_unrotated_cropbox() -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    selection = PageRegionSelection.for_full_page(source, 2)

    result = PyMuPdfRegionRenderer(resolution_dpi=72).render(
        source, BytesIO(payload), (selection,)
    )[0]

    assert result.selection_was_full_page is True
    assert result.source_bounding_box == (0.0, 0.0, 200.0, 300.0)
    assert result.coordinate_system == PYMUPDF_COORDINATE_SYSTEM
    assert (result.width_pixels, result.height_pixels) == (300, 200)
    assert result.media_type == "image/png"
    assert result.byte_length == len(result.content)
    assert result.alpha is False


def test__renderer__preserves_printed_page_label_exactly() -> None:
    document = pymupdf.open()
    document.new_page()
    document.set_page_labels(
        [{"startpage": 0, "prefix": " A ", "style": "D", "firstpagenum": 1}]
    )
    payload = document.tobytes()
    document.close()
    source = _source(payload)

    result = PyMuPdfRegionRenderer(resolution_dpi=72).render(
        source,
        BytesIO(payload),
        (PageRegionSelection.for_full_page(source, 0),),
    )[0]

    assert result.printed_page_label == " A 1"


def test__renderer__stable_identity_and_configuration() -> None:
    payload = _fixture_pdf()
    first_source = _source(payload, "file:///first.pdf")
    second_source = _source(payload, "https://example.test/second.pdf")
    first_selection = PageRegionSelection.for_bounding_box(
        first_source, 0, (0, 0, 150, 200)
    )
    second_selection = PageRegionSelection.for_bounding_box(
        second_source, 0, (0, 0, 150, 200)
    )

    rgb_renderer = PyMuPdfRegionRenderer(
        resolution_dpi=72, color_mode=RegionColorMode.RGB
    )
    first = rgb_renderer.render(
        first_source, BytesIO(payload), (first_selection,)
    )[0]
    rerun = rgb_renderer.render(
        second_source, BytesIO(payload), (second_selection,)
    )[0]
    grayscale = PyMuPdfRegionRenderer(
        resolution_dpi=72, color_mode=RegionColorMode.GRAYSCALE
    ).render(first_source, BytesIO(payload), (first_selection,))[0]
    high_resolution = PyMuPdfRegionRenderer(resolution_dpi=144).render(
        first_source, BytesIO(payload), (first_selection,)
    )[0]

    assert first.content == rerun.content
    assert first.content_sha256 == rerun.content_sha256
    assert first.region_id == rerun.region_id
    assert first.configuration_digest == rgb_renderer.configuration_digest
    assert grayscale.content_sha256 != first.content_sha256
    assert grayscale.region_id != first.region_id
    assert high_resolution.content_sha256 != first.content_sha256
    assert high_resolution.region_id != first.region_id
    assert (high_resolution.width_pixels, high_resolution.height_pixels) == (
        300,
        400,
    )
    assert first.processor_name == "pymupdf-region-renderer"
    assert first.processor_version == "1"
    assert first.backend_name == "pymupdf"
    assert first.backend_version == pymupdf.__version__


def test__rendered_region__rejects_identity_evidence_tampering() -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    selection = PageRegionSelection.for_bounding_box(
        source, 0, (0, 0, 150, 200)
    )
    result = PyMuPdfRegionRenderer(resolution_dpi=72).render(
        source, BytesIO(payload), (selection,)
    )[0]

    for changes in (
        {"region_id": "rendered-region:sha256:" + "0" * 64},
        {"source_bounding_box": (1.0, 1.0, 149.0, 199.0)},
        {"configuration_digest": "configuration:sha256:" + "0" * 64},
        {"resolution_dpi": 73},
        {"backend_version": "tampered-backend"},
    ):
        with pytest.raises(ValueError, match="ID does not match"):
            replace(result, **changes)


def test__renderer__rejects_empty_invalid_and_out_of_page_selections() -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    renderer = PyMuPdfRegionRenderer()

    with pytest.raises(ValueError, match="at least one"):
        renderer.render(source, BytesIO(payload), ())
    with pytest.raises(ValueError, match="outside the PDF"):
        renderer.render(
            source,
            BytesIO(payload),
            (PageRegionSelection.for_full_page(source, 3),),
        )
    with pytest.raises(ValueError, match="outside the page crop box"):
        renderer.render(
            source,
            BytesIO(payload),
            (
                PageRegionSelection.for_bounding_box(
                    source, 0, (0, 0, 300.0001, 200)
                ),
            ),
        )


def test__renderer__bounds_iterable_before_materializing_request() -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    selection = PageRegionSelection.for_full_page(source, 0)
    consumed = 0

    def selections():
        nonlocal consumed
        while True:
            consumed += 1
            if consumed > 3:
                raise AssertionError("renderer consumed beyond limit plus one")
            yield selection

    with pytest.raises(PdfRegionRenderLimitError, match="max_selections"):
        PyMuPdfRegionRenderer(max_selections=2).render(
            source,
            BytesIO(payload),
            selections(),
        )

    assert consumed == 3


def test__renderer__checks_aggregate_limits_before_raster_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    selections = (
        PageRegionSelection.for_full_page(source, 0),
        PageRegionSelection.for_full_page(source, 1),
    )

    def unexpected_render(*args: object, **kwargs: object) -> None:
        raise AssertionError("get_pixmap was called before aggregate rejection")

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", unexpected_render)

    with pytest.raises(PdfRegionRenderLimitError, match="max_total_pixels"):
        PyMuPdfRegionRenderer(
            resolution_dpi=72,
            max_pixels=60_000,
            max_raster_bytes=180_000,
            max_total_pixels=100_000,
            max_total_raster_bytes=300_000,
        ).render(source, BytesIO(payload), selections)


def test__renderer__checks_resource_limits_before_raster_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    selection = PageRegionSelection.for_full_page(source, 0)

    def unexpected_render(*args: object, **kwargs: object) -> None:
        raise AssertionError("get_pixmap was called before limit rejection")

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", unexpected_render)

    with pytest.raises(
        PdfRegionRenderLimitError,
        match="max_dimension_pixels",
    ):
        PyMuPdfRegionRenderer(
            resolution_dpi=2400,
            max_dimension_pixels=1000,
        ).render(source, BytesIO(payload), (selection,))


def test__renderer__records_fractional_pixel_mapping() -> None:
    document = pymupdf.open()
    for rotation in (0, 90, 180, 270):
        page = document.new_page(width=100, height=80)
        page.draw_rect((0, 0, 50, 80), color=(1, 0, 0), fill=(1, 0, 0))
        page.draw_rect((50, 0, 100, 80), color=(0, 0, 1), fill=(0, 0, 1))
        page.set_rotation(rotation)
    payload = document.tobytes()
    document.close()
    source = _source(payload)
    requested_box = (49.25, 10.25, 50.75, 20.75)
    selections = tuple(
        PageRegionSelection.for_bounding_box(source, page_index, requested_box)
        for page_index in range(4)
    )

    results = PyMuPdfRegionRenderer(resolution_dpi=96).render(
        source, BytesIO(payload), selections
    )

    assert [result.page_rotation_degrees for result in results] == [
        0,
        90,
        180,
        270,
    ]
    assert all(
        result.width_pixels == 3 and result.height_pixels in (14, 15)
        for result in (results[0], results[2])
    )
    assert all(
        result.width_pixels in (14, 15) and result.height_pixels == 3
        for result in (results[1], results[3])
    )
    for result in results:
        assert result.source_bounding_box == requested_box
        a, b, c, d, e, f = result.pixel_to_source_matrix
        corners = (
            (e, f),
            (result.width_pixels * a + e, result.width_pixels * b + f),
            (result.height_pixels * c + e, result.height_pixels * d + f),
            (
                result.width_pixels * a + result.height_pixels * c + e,
                result.width_pixels * b + result.height_pixels * d + f,
            ),
        )
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        assert result.effective_source_bounding_box == pytest.approx(
            (min(xs), min(ys), max(xs), max(ys))
        )
        effective = result.effective_source_bounding_box
        assert effective[0] <= requested_box[0]
        assert effective[1] <= requested_box[1]
        assert effective[2] >= requested_box[2]
        assert effective[3] >= requested_box[3]
        raster = pymupdf.Pixmap(result.content)
        colors = {
            tuple(raster.samples[offset : offset + 3])
            for offset in range(0, len(raster.samples), raster.n)
        }
        assert any(red > blue for red, _, blue in colors)
        assert any(blue > red for red, _, blue in colors)


def test__renderer__validates_exact_source_and_reports_pdf_failures() -> None:
    payload = _fixture_pdf()
    source = _source(payload)
    selection = PageRegionSelection.for_full_page(source, 0)

    with pytest.raises(ValueError, match="do not agree"):
        PyMuPdfRegionRenderer().render(
            source,
            BytesIO(payload + b"changed"),
            (selection,),
        )

    malformed = b"not a PDF"
    malformed_source = _source(malformed)
    with pytest.raises(pymupdf.FileDataError):
        PyMuPdfRegionRenderer().render(
            malformed_source,
            BytesIO(malformed),
            (PageRegionSelection.for_full_page(malformed_source, 0),),
        )

    document = pymupdf.open()
    document.new_page()
    encrypted = document.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()
    encrypted_source = _source(encrypted)
    with pytest.raises(ValueError, match="encrypted PDF requires a password"):
        PyMuPdfRegionRenderer().render(
            encrypted_source,
            BytesIO(encrypted),
            (PageRegionSelection.for_full_page(encrypted_source, 0),),
        )
