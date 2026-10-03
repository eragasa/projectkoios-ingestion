from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pytest
from projectkoios.ingestion import (
    DeterministicFigureCandidateDetector,
    FigureDetectionConfiguration,
    PyMuPdfExtractor,
    PyMuPdfFigureInspector,
    SourceDocument,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    IngestionWarning,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)

pymupdf = pytest.importorskip("pymupdf")


def _solid_png() -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 16, 12))
    pixmap.clear_with(0x2D6A9F)
    return pixmap.tobytes("png")


def _embedded_pdf() -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page(width=500, height=380)
    page.insert_image((90, 55, 330, 215), stream=_solid_png())
    payload = pdf.tobytes()
    pdf.close()
    return payload


def test__figure_detector__retains_but_does_not_promote_scanline_images() -> (
    None
):
    pdf = pymupdf.open()
    page = pdf.new_page(width=500, height=380)
    page.insert_image((90, 55, 330, 55.125), stream=_solid_png())
    payload = pdf.tobytes()
    pdf.close()
    source = SourceDocument.from_bytes(
        payload,
        source_id="article:figure:scanline-image",
        media_type="application/pdf",
        locator="memory://figure-scanline-image.pdf",
    )
    extracted = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    detector = DeterministicFigureCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer()
    )

    result = detector.detect(extracted, BytesIO(payload))

    assert len(result.detection_input.page_evidence[0].embedded_artifacts) == 1
    assert result.candidates == ()


@pytest.mark.parametrize(
    ("raw_bounding_box", "reason"),
    (
        (
            (
                49.707000732421875,
                372.2469787597656,
                162.9169921875,
                372.2460021972656,
            ),
            "unordered",
        ),
        ((490.0, 55.0, 500.1, 215.0), "outside_page"),
    ),
)
def test__figure_inspector__skips_warned_unlocated_image_evidence(
    monkeypatch: pytest.MonkeyPatch,
    raw_bounding_box: tuple[float, float, float, float],
    reason: str,
) -> None:
    payload = _embedded_pdf()
    source = SourceDocument.from_bytes(
        payload,
        source_id="article:figure:unlocated-image",
        media_type="application/pdf",
        locator="memory://figure-unlocated-image.pdf",
    )
    extracted = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    image_block = next(
        block for block in extracted.pages[0].blocks if block.kind == "image"
    )
    unlocated_span = replace(image_block.source_spans[0], bounding_box=None)
    warning = IngestionWarning.create(
        code="pdf.invalid_block_geometry",
        severity=WarningSeverity.WARNING,
        message="invalid backend geometry",
        object_ids=(unlocated_span.source_object_id or "",),
        source_spans=(unlocated_span,),
        evidence=(("geometry_reason", reason),),
    )
    unlocated_block = ExtractedBlock.create(
        kind=image_block.kind,
        source_spans=(unlocated_span,),
        extraction_method=image_block.extraction_method,
        confidence=image_block.confidence,
        asset_id=image_block.asset_id,
        warning_ids=(warning.warning_id,),
        asset_media_type=image_block.asset_media_type,
        asset_mask_id=image_block.asset_mask_id,
        asset_mask_media_type=image_block.asset_mask_media_type,
    )
    extracted_page = extracted.pages[0]
    unlocated_page = replace(
        extracted_page,
        blocks=tuple(
            unlocated_block if block is image_block else block
            for block in extracted_page.blocks
        ),
        warning_ids=(warning.warning_id,),
    )
    unlocated_document = ExtractedDocument.create(
        source=source,
        pages=(unlocated_page,),
        metadata=extracted.metadata,
        warning_ids=(warning.warning_id,),
    )

    backend_document = pymupdf.open(stream=payload, filetype="pdf")
    backend_page = backend_document[0]
    raw = backend_page.get_text("dict", sort=False)
    raw_image = next(block for block in raw["blocks"] if block.get("type") == 1)
    raw_image["bbox"] = raw_bounding_box
    width = float(backend_page.cropbox.width)
    height = float(backend_page.cropbox.height)
    rotation = int(backend_page.rotation)
    backend_document.close()

    class FakePage:
        cropbox = type("CropBox", (), {"width": width, "height": height})()

        def __init__(self) -> None:
            self.rotation = rotation

        def get_text(self, kind: str, *, sort: bool) -> dict[str, object]:
            assert kind == "dict"
            assert sort is False
            return raw

        def get_drawings(self) -> list[dict[str, object]]:
            return []

    class FakeDocument:
        def __len__(self) -> int:
            return 1

        def __getitem__(self, index: int) -> FakePage:
            assert index == 0
            return FakePage()

        def close(self) -> None:
            return None

    monkeypatch.setattr(pymupdf, "open", lambda **_kwargs: FakeDocument())
    inspector = PyMuPdfFigureInspector()

    first = inspector.inspect(
        unlocated_document,
        BytesIO(payload),
        FigureDetectionConfiguration(),
    )
    second = inspector.inspect(
        unlocated_document,
        BytesIO(payload),
        FigureDetectionConfiguration(),
    )

    assert first == second
    assert first[0].embedded_artifacts == ()
