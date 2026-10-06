from __future__ import annotations

import math

import pytest
from projectkoios.ingestion import (
    PyMuPdfExtractor as RootPyMuPdfExtractor,
)
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf import PyMuPdfExtractor
from projectkoios.ingestion.pdf.adapters.pymupdf.extraction import (
    PyMuPdfExtractor as AdapterPyMuPdfExtractor,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


class _FakeCropBox:
    width = 612.0
    height = 792.0


class _FakePage:
    cropbox = _FakeCropBox()
    rotation = 0

    def __init__(self, blocks: list[dict[str, object]]) -> None:
        self._blocks = blocks

    def get_text(self, kind: str, *, sort: bool) -> dict[str, object]:
        assert kind == "dict"
        assert sort is False
        return {"blocks": self._blocks}

    def get_label(self) -> str:
        return "80"


def _source() -> SourceDocument:
    return SourceDocument.from_bytes(
        b"%PDF-1.7\ninvalid geometry fixture\n%%EOF\n",
        source_id="article:invalid-geometry",
        media_type="application/pdf",
        locator="memory://invalid-geometry.pdf",
    )


def _raw_text_block(
    bounding_box: object,
    *,
    text: str = "Retained text evidence",
) -> dict[str, object]:
    return {
        "type": 0,
        "bbox": bounding_box,
        "lines": [{"spans": [{"text": text}]}],
    }


def test__pymupdf_extractor__preserves_established_facade_exports() -> None:
    assert PyMuPdfExtractor is AdapterPyMuPdfExtractor
    assert RootPyMuPdfExtractor is AdapterPyMuPdfExtractor
    assert AdapterPyMuPdfExtractor.__module__ == (
        "projectkoios.ingestion.pdf.adapters.pymupdf.extraction"
    )


def test__pymupdf__invalid_image_box_is_warned_and_preserved() -> None:
    source = _source()
    valid_box = (10.0, 20.0, 30.0, 40.0)
    simon_box = (
        49.707000732421875,
        372.2469787597656,
        162.9169921875,
        372.2460021972656,
    )
    page = _FakePage(
        [
            _raw_text_block(valid_box),
            {
                "type": 1,
                "bbox": simon_box,
                "image": b"retained-image-bytes",
                "ext": "png",
            },
        ]
    )
    extractor = AdapterPyMuPdfExtractor(low_text_character_threshold=0)

    extracted, warnings = extractor._extract_page(source, page, 79)

    assert len(extracted.blocks) == 2
    text, image = extracted.blocks
    assert text.source_spans[0].bounding_box == valid_box
    assert text.warning_ids == ()
    assert image.asset_id == (
        "asset:sha256:"
        + SHA256Fingerprinter.fingerprint(content=b"retained-image-bytes")
    )
    assert image.source_spans[0].source_object_id == "page:79:block:1"
    assert image.source_spans[0].bounding_box is None
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.code == "pdf.invalid_block_geometry"
    assert warning.object_ids == ("page:79:block:1",)
    assert warning.source_spans == image.source_spans
    assert warning.evidence == (
        ("block_type", "image"),
        ("geometry_reason", "unordered"),
        (
            "raw_bounding_box",
            "49.707000732421875,372.24697875976562,"
            "162.9169921875,372.24600219726562",
        ),
    )
    assert image.warning_ids == (warning.warning_id,)
    assert extracted.warning_ids == (warning.warning_id,)


def test__pymupdf__preserves_outside_page_image_without_geometry() -> None:
    source = _source()
    image = b"outside-page-image"
    page = _FakePage(
        [
            {
                "type": 1,
                "bbox": (600.0, 10.0, 612.0001, 30.0),
                "image": image,
                "ext": "png",
            }
        ]
    )
    extractor = AdapterPyMuPdfExtractor(low_text_character_threshold=0)

    extracted, warnings = extractor._extract_page(source, page, 0)

    assert len(extracted.blocks) == 1
    block = extracted.blocks[0]
    assert block.asset_id == "asset:sha256:" + SHA256Fingerprinter.fingerprint(
        content=image
    )
    assert block.source_spans[0].bounding_box is None
    assert block.source_spans[0].source_object_id == "page:0:block:0"
    assert len(warnings) == 1
    assert warnings[0].code == "pdf.invalid_block_geometry"
    assert warnings[0].object_ids == ("page:0:block:0",)
    assert warnings[0].source_spans == block.source_spans
    assert warnings[0].evidence == (
        ("block_type", "image"),
        ("geometry_reason", "outside_page"),
        ("raw_bounding_box", "600,10,612.00009999999997,30"),
    )
    assert block.warning_ids == (warnings[0].warning_id,)


@pytest.mark.parametrize(
    ("bounding_box", "reason"),
    (
        ("not-a-bounding-box", "malformed"),
        ((0.0, 0.0, 1.0), "malformed"),
        ((0.0, 0.0, math.nan, 1.0), "non_finite"),
        ((-0.001, 0.0, 1.0, 1.0), "negative_coordinate"),
        ((2.0, 0.0, 1.0, 1.0), "unordered"),
        ((0.0, 1.0, 1.0, 1.0), "non_positive_area"),
    ),
)
def test__pymupdf_extractor__invalid_text_geometry_replays_without_box(
    bounding_box: object,
    reason: str,
) -> None:
    source = _source()
    page = _FakePage([_raw_text_block(bounding_box)])
    extractor = AdapterPyMuPdfExtractor(low_text_character_threshold=0)

    first = extractor._extract_page(source, page, 0)
    second = extractor._extract_page(source, page, 0)

    assert first == second
    extracted, warnings = first
    assert extracted.blocks[0].text == "Retained text evidence"
    assert extracted.blocks[0].source_spans[0].bounding_box is None
    assert warnings[0].evidence[1] == ("geometry_reason", reason)
    assert warnings[0].object_ids == ("page:0:block:0",)
    assert extracted.blocks[0].warning_ids == (warnings[0].warning_id,)
