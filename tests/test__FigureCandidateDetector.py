from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from projectkoios.ingestion import (
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    FigureArtifactKind,
    FigureAssociationRole,
    FigureCandidateDetector,
    FigureDetectionConfiguration,
    FigureDetectionLimitError,
    FigureEvidenceStatus,
    PyMuPdfExtractor,
    SourceDocument,
)

pymupdf = pytest.importorskip("pymupdf")


def _source(payload: bytes, suffix: str) -> SourceDocument:
    return SourceDocument.from_bytes(
        payload,
        source_id=f"article:figure:{suffix}",
        media_type="application/pdf",
        locator=f"memory://figure-{suffix}.pdf",
    )


def _extract(payload: bytes, suffix: str):
    source = _source(payload, suffix)
    document = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    return source, document


def _detect(
    payload: bytes,
    suffix: str,
    configuration: FigureDetectionConfiguration | None = None,
):
    _, document = _extract(payload, suffix)
    detector: FigureCandidateDetector = DeterministicFigureCandidateDetector(
        configuration
    )
    return detector.detect(document, BytesIO(payload))


def _solid_png(color: int = 0x2D6A9F) -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 16, 12))
    pixmap.clear_with(color)
    return pixmap.tobytes("png")


def _embedded_pdf(*, caption: bool = True, subfigures: bool = False) -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page(width=500, height=380)
    if subfigures:
        page.insert_image((55, 55, 215, 175), stream=_solid_png(0x2D6A9F))
        page.insert_image((285, 55, 445, 175), stream=_solid_png(0x9F6A2D))
        page.insert_text((120, 190), "(a)", fontsize=10)
        page.insert_text((350, 205), "(b)", fontsize=10)
        if caption:
            page.insert_text(
                (55, 230), "Figure 7. Two synthetic panels.", fontsize=11
            )
    else:
        page.insert_image((90, 55, 330, 215), stream=_solid_png())
        if caption:
            page.insert_text(
                (72, 240), "Figure 1. Synthetic image caption.", fontsize=11
            )
    payload = pdf.tobytes()
    pdf.close()
    return payload


def _drawing_pdf() -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page(width=500, height=400)
    page.draw_line((80, 230), (300, 230), color=(0, 0, 0), width=1)
    page.draw_line((80, 70), (80, 230), color=(0, 0, 0), width=1)
    page.draw_line((100, 180), (280, 180), color=(0, 0, 1), width=2)
    page.draw_line((280, 100), (280, 180), color=(0, 0, 1), width=2)
    page.insert_text((115, 120), "Legend: blue series", fontsize=10)
    page.insert_text(
        (80, 260), "Figure 2. Vector diagram evidence.", fontsize=11
    )
    payload = pdf.tobytes()
    pdf.close()
    return payload


def test__figure_detector__detects_maintained_embedded_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "figures.pdf"
    result = _detect(fixture.read_bytes(), "fixture")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.source_label == "Figure 1"
    assert candidate.evidence_status is FigureEvidenceStatus.PROPOSED
    assert candidate.warning_ids == ()
    assert len(candidate.components) == 1
    component = candidate.components[0]
    assert component.artifact_kind is FigureArtifactKind.EMBEDDED_IMAGE
    assert component.rendered_region is None
    assert component.source_bounding_box == (90.0, 55.0, 330.0, 215.0)
    assert tuple(item.role for item in candidate.associations) == (
        FigureAssociationRole.CAPTION,
    )
    assert candidate.associations[0].text == (
        "Figure 1. Synthetic blue rectangle caption."
    )
    artifact = result.detection_input.page_evidence[0].embedded_artifacts[0]
    assert artifact.artifact_id == component.embedded_artifact_id
    assert artifact.asset_id == f"asset:sha256:{artifact.content_sha256}"
    assert artifact.byte_length == len(artifact.content)
    assert artifact.width_pixels > 0
    assert artifact.height_pixels > 0
    assert artifact.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert artifact.source_spans == component.source_spans


def test__figure_detector__retains_embedded_image_mask_bytes() -> None:
    image = pymupdf.Pixmap(
        pymupdf.csRGB,
        pymupdf.IRect(0, 0, 8, 8),
        True,
    )
    image.clear_with(0x33669980)
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=260)
    page.insert_image((60, 40, 240, 180), stream=image.tobytes("png"))
    page.insert_text((60, 210), "Figure 3. Transparent image.", fontsize=11)
    payload = pdf.tobytes()
    pdf.close()

    result = _detect(payload, "mask")

    artifact = result.detection_input.page_evidence[0].embedded_artifacts[0]
    assert artifact.mask_content is not None
    assert artifact.mask_content_sha256 is not None
    assert artifact.mask_asset_id == (
        f"asset:sha256:{artifact.mask_content_sha256}"
    )
    assert artifact.mask_byte_length == len(artifact.mask_content)
    assert artifact.mask_media_type == "image/png"


def test__figure_detector__renders_pdf_drawing_diagram_and_links_legend() -> (
    None
):
    payload = _drawing_pdf()

    result = _detect(payload, "drawing")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.source_label == "Figure 2"
    assert tuple(item.role for item in candidate.associations) == (
        FigureAssociationRole.CAPTION,
        FigureAssociationRole.LEGEND,
    )
    component = candidate.components[0]
    assert component.artifact_kind is FigureArtifactKind.RENDERED_DRAWING
    assert component.source_block_ids == ()
    assert component.drawing_evidence_ids
    assert component.source_spans
    assert component.rendered_region is not None
    assert component.rendered_region.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert component.rendered_region.content_sha256
    x0, y0, x1, y1 = component.rendered_region.source_bounding_box
    assert 0.0 <= x0 < x1 <= 500.0
    assert 0.0 <= y0 < y1 <= 400.0
    cx0, cy0, cx1, cy1 = component.source_bounding_box
    assert x0 <= cx0 < cx1 <= x1
    assert y0 <= cy0 < cy1 <= y1


def test__figure_detector__groups_subfigures_and_preserves_labels() -> None:
    result = _detect(_embedded_pdf(subfigures=True), "subfigures")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.source_label == "Figure 7"
    assert len(candidate.components) == 2
    assert tuple(
        component.component_index for component in candidate.components
    ) == (
        0,
        1,
    )
    assert tuple(item.role for item in candidate.associations) == (
        FigureAssociationRole.CAPTION,
        FigureAssociationRole.SUBFIGURE_LABEL,
        FigureAssociationRole.SUBFIGURE_LABEL,
    )
    labels = candidate.associations[1:]
    assert tuple(label.text for label in labels) == ("(a)", "(b)")
    assert tuple(label.component_id for label in labels) == tuple(
        component.component_id for component in candidate.components
    )


def test__figure_detector__keeps_captionless_image_ambiguous() -> None:
    result = _detect(_embedded_pdf(caption=False), "captionless")

    candidate = result.candidates[0]
    assert candidate.source_label is None
    assert candidate.associations == ()
    assert candidate.evidence_status is FigureEvidenceStatus.AMBIGUOUS
    assert tuple(warning.code for warning in result.warnings) == (
        "figure.caption_missing",
        "figure.low_confidence",
    )
    assert candidate.warning_ids == tuple(
        warning.warning_id for warning in result.warnings
    )


def test__figure_detector__uses_only_expected_matrix_fixtures() -> None:
    fixture_directory = Path(__file__).parent / "fixtures" / "pdf"
    detected = {
        fixture.stem: len(
            _detect(fixture.read_bytes(), f"matrix-{fixture.stem}").candidates
        )
        for fixture in sorted(fixture_directory.glob("*.pdf"))
    }

    assert detected["figures"] == 1
    assert detected["image-only-page"] == 1
    assert all(
        count == 0
        for name, count in detected.items()
        if name not in {"figures", "image-only-page"}
    )


def test__figure_detector__does_not_promote_unassociated_table_rules() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "tables.pdf"
    result = _detect(fixture.read_bytes(), "table-rules")

    assert result.candidates == ()
    assert tuple(warning.code for warning in result.warnings) == (
        "figure.unassociated_drawing_ignored",
    )
    assert result.detection_input.page_evidence[0].drawings


def test__figure_detector__rejects_wrong_source_and_stale_layout() -> None:
    payload = _embedded_pdf()
    _, document = _extract(payload, "exact")
    other_source = _source(payload, "other")
    other_document = (
        PyMuPdfExtractor().extract(other_source, BytesIO(payload)).document
    )
    stale_layouts = DeterministicLayoutProcessor().analyze(other_document)
    detector = DeterministicFigureCandidateDetector()

    wrong_payload = bytearray(payload)
    wrong_payload[-1] ^= 1
    with pytest.raises(ValueError, match="hash does not match"):
        detector.detect(document, BytesIO(bytes(wrong_payload)))
    with pytest.raises(ValueError, match="stale or inconsistent"):
        detector.detect_with_layout(document, BytesIO(payload), stale_layouts)


def test__figure_detector__enforces_asset_limit_before_rendering() -> None:
    payload = _embedded_pdf()
    _, document = _extract(payload, "limit")

    class RejectRenderer:
        name = "reject-renderer"
        version = "1"

        def render(self, *_args: Any, **_kwargs: Any):
            raise AssertionError("renderer must not be called")

    detector = DeterministicFigureCandidateDetector(
        FigureDetectionConfiguration(max_embedded_asset_bytes=32),
        region_renderer=RejectRenderer(),  # type: ignore[arg-type]
    )

    with pytest.raises(
        FigureDetectionLimitError, match="max_embedded_asset_bytes"
    ):
        detector.detect(document, BytesIO(payload))


def test__figure_detector__bounds_drawing_group_work_before_rendering() -> None:
    payload = _drawing_pdf()
    _, document = _extract(payload, "drawing-group-limit")

    class RejectRenderer:
        name = "reject-renderer"
        version = "1"

        def render(self, *_args: Any, **_kwargs: Any):
            raise AssertionError("renderer must not be called")

    detector = DeterministicFigureCandidateDetector(
        FigureDetectionConfiguration(max_drawing_group_comparisons=1),
        region_renderer=RejectRenderer(),  # type: ignore[arg-type]
    )

    with pytest.raises(
        FigureDetectionLimitError,
        match="max_drawing_group_comparisons",
    ):
        detector.detect(document, BytesIO(payload))


def test__figure_detector__bounds_association_work_before_rendering() -> None:
    payload = _drawing_pdf()
    _, document = _extract(payload, "comparison-limit")

    class RejectRenderer:
        name = "reject-renderer"
        version = "1"

        def render(self, *_args: Any, **_kwargs: Any):
            raise AssertionError("renderer must not be called")

    detector = DeterministicFigureCandidateDetector(
        FigureDetectionConfiguration(max_association_comparisons=1),
        region_renderer=RejectRenderer(),  # type: ignore[arg-type]
    )

    with pytest.raises(
        FigureDetectionLimitError,
        match="max_association_comparisons",
    ):
        detector.detect(document, BytesIO(payload))


def test__figure_detector__enforces_rendered_png_aggregate_limit() -> None:
    payload = _drawing_pdf()

    with pytest.raises(
        FigureDetectionLimitError,
        match="max_total_rendered_png_bytes",
    ):
        _detect(
            payload,
            "render-limit",
            FigureDetectionConfiguration(max_total_rendered_png_bytes=1),
        )


def test__figure_detector__identity_is_stable_and_configuration_bound() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "figures.pdf"
    payload = fixture.read_bytes()

    first = _detect(payload, "identity")
    second = _detect(payload, "identity")
    changed = _detect(
        payload,
        "identity",
        FigureDetectionConfiguration(association_distance_points=97.0),
    )

    assert first == second
    assert first.result_id == second.result_id
    assert first.result_id != changed.result_id
    assert first.detection_input.input_id != changed.detection_input.input_id


def test__figure_detector__contracts_are_immutable_and_reject_stale_ids() -> (
    None
):
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "figures.pdf"
    result = _detect(fixture.read_bytes(), "immutable")
    candidate = result.candidates[0]

    with pytest.raises(FrozenInstanceError):
        candidate.confidence = 0.0  # type: ignore[misc]
    with pytest.raises(ValueError, match="detection-input ID is inconsistent"):
        replace(result.detection_input, input_id="stale-input")
    with pytest.raises(ValueError, match="candidate ID is inconsistent"):
        replace(candidate, confidence=0.0)
    with pytest.raises(ValueError, match="component ID is inconsistent"):
        replace(candidate.components[0], confidence=0.0)
    with pytest.raises(ValueError, match="detection-result ID is inconsistent"):
        replace(result, result_id="figure-result:sha256:" + "0" * 64)
