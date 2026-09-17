#!/usr/bin/env python3
"""Generate and verify the redistributable cold-PDF fixture matrix.

The committed PDF bytes, not a fresh generation run, are the test inputs.  See
``tests/fixtures/pdf/README.md`` for the version-sensitive refresh workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[1]
FIXTURE_DIRECTORY = ROOT / "tests" / "fixtures" / "pdf"
MANIFEST_PATH = FIXTURE_DIRECTORY / "manifest.json"
SRC = ROOT / "src" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from projectkoios.ingestion.models import SourceDocument  # noqa: E402
from projectkoios.ingestion.pdf import PyMuPdfExtractor  # noqa: E402


@dataclass(frozen=True)
class FixtureCase:
    fixture_id: str
    purpose: str
    assertions: tuple[str, ...]
    build: Callable[[Any], Any]


def _new_document(pymupdf: Any) -> Any:
    document = pymupdf.open()
    document.set_metadata(
        {
            "title": "Project Koios synthetic PDF fixture",
            "author": "Eugene Ragasa",
            "subject": "Redistributable cold-extraction test evidence",
            "creator": "scripts/pdf_fixture_matrix.py",
            "producer": "PyMuPDF",
        }
    )
    return document


def _born_digital(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=420, height=300)
    page.insert_textbox(
        (54, 54, 366, 150),
        "Born-digital text evidence\nAlpha beta gamma delta\n"
        "Native text remains raw extraction evidence.",
        fontsize=11,
    )
    return document


def _two_column(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=600, height=420)
    # Deliberately insert the right column first: cold extraction promises the
    # backend's native block order, not inferred reading order.
    page.insert_textbox(
        (330, 72, 546, 250),
        "RIGHT COLUMN FIRST\nRight line two\nRight line three",
        fontsize=11,
    )
    page.insert_textbox(
        (54, 72, 270, 250),
        "LEFT COLUMN SECOND\nLeft line two\nLeft line three",
        fontsize=11,
    )
    return document


def _spanning_heading(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=600, height=420)
    # Insert columns before the heading so native order differs from the
    # geometry-derived proposal.
    page.insert_textbox(
        (330, 92, 546, 260),
        "RIGHT COLUMN\nRight flow one\nRight flow two",
        fontsize=11,
    )
    page.insert_textbox(
        (54, 92, 270, 260),
        "LEFT COLUMN\nLeft flow one\nLeft flow two",
        fontsize=11,
    )
    page.insert_textbox(
        (54, 36, 546, 68),
        "SPANNING HEADING ACROSS BOTH COLUMNS -----------------------",
        fontsize=11,
    )
    return document


def _footnote(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=420, height=420)
    # Insert the footnote first so native order differs from the supported
    # main-flow-then-footnote layout proposal.
    page.insert_textbox(
        (54, 340, 366, 380),
        "1 Footnote evidence near the separated page bottom.",
        fontsize=9,
    )
    page.insert_textbox(
        (54, 54, 366, 210),
        "Main flow evidence\nFirst body line\nSecond body line",
        fontsize=11,
    )
    return document


def _sidebar(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=600, height=420)
    page.insert_textbox(
        (54, 72, 390, 280),
        "MAIN FLOW HAS A SUBSTANTIALLY WIDER MEASURE\n"
        "Main line two remains concurrent with side text\n"
        "Main line three remains geometry evidence",
        fontsize=11,
    )
    page.insert_textbox(
        (470, 92, 550, 220),
        "SIDE\nNOTE\nMAYBE",
        fontsize=10,
    )
    return document


def _ambiguous_overlap(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=420, height=300)
    page.insert_textbox(
        (54, 80, 150, 170),
        "LEFT MAYBE\nConcurrent\nuncertain",
        fontsize=11,
    )
    page.insert_textbox(
        (132, 82, 232, 172),
        "RIGHT MAYBE\nConcurrent\nuncertain",
        fontsize=11,
    )
    return document


def _equations(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=420, height=300)
    page.insert_textbox(
        (54, 48, 366, 100),
        "Equation page: raw native characters only",
        fontsize=11,
    )
    page.insert_textbox(
        (120, 125, 300, 175),
        "E = m c^2    (1)",
        fontsize=13,
    )
    page.insert_textbox(
        (54, 205, 366, 250),
        "No equation interpretation is asserted.",
        fontsize=11,
    )
    return document


def _tables(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=540, height=320)
    page.insert_text((60, 52), "Table evidence: positioned native text")
    boxes = (
        (60, 86, 220, 130),
        (310, 86, 470, 130),
        (60, 146, 220, 190),
        (310, 146, 470, 190),
    )
    values = (
        "Header A\ncolumn one",
        "Header B\ncolumn two",
        "Cell A1\nrow one",
        "Cell B1\nrow one",
    )
    for box, value in zip(boxes, values, strict=True):
        page.insert_textbox(box, value, fontsize=11)
    for x in (54, 270, 486):
        page.draw_line((x, 82), (x, 192), width=0.5)
    for y in (82, 132, 192):
        page.draw_line((54, y), (486, y), width=0.5)
    return document


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(
        ">I", checksum
    )


def _solid_png(color: int) -> bytes:
    """Return a synthetic RGB PNG with no embedded metadata or ICC profile."""
    width = 16
    height = 16
    red = (color >> 16) & 0xFF
    green = (color >> 8) & 0xFF
    blue = color & 0xFF
    row = b"\x00" + bytes((red, green, blue)) * width
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(row * height, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _insert_profile_free_image(
    document: Any,
    page: Any,
    rectangle: tuple[int, int, int, int],
    color: int,
) -> None:
    image_xref = page.insert_image(rectangle, stream=_solid_png(color))
    # PyMuPDF otherwise attaches its bundled default ICC profile. DeviceRGB is
    # sufficient for this synthetic solid-color evidence and leaves no
    # dependency-supplied profile in the redistributable PDF.
    document.xref_set_key(image_xref, "ColorSpace", "/DeviceRGB")


def _figures(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=420, height=340)
    _insert_profile_free_image(document, page, (90, 55, 330, 215), 0x2D6A9F)
    page.insert_textbox(
        (72, 235, 348, 285),
        "Figure 1. Synthetic blue rectangle caption.",
        fontsize=11,
    )
    return document


def _page_labels(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    first = document.new_page(width=420, height=300)
    first.insert_text(
        (54, 72), "First physically ordered labeled page evidence"
    )
    second = document.new_page(width=420, height=300)
    second.insert_text(
        (54, 72), "Second physically ordered labeled page evidence"
    )
    document.set_page_labels(
        [{"startpage": 0, "prefix": "App-", "style": "A", "firstpagenum": 1}]
    )
    return document


def _blank_page(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    document.new_page(width=420, height=300)
    return document


def _image_only(pymupdf: Any) -> Any:
    document = _new_document(pymupdf)
    page = document.new_page(width=420, height=300)
    _insert_profile_free_image(document, page, (72, 54, 348, 246), 0x8A4F2D)
    return document


CASES = (
    FixtureCase(
        "born-digital-text",
        "Native born-digital text extraction.",
        (
            "one physical page is retained",
            "native text and its block geometry are retained",
            "the page has no cold-extraction warning",
        ),
        _born_digital,
    ),
    FixtureCase(
        "two-column-layout",
        "Extractor-native evidence for a synthetic two-column page.",
        (
            "right-column text precedes left-column text in native block order",
            "separated block geometry remains available to layout processing",
            "cold extraction emits no derived reading-order warning",
        ),
        _two_column,
    ),
    FixtureCase(
        "spanning-heading",
        "A page-wide heading before two concurrent text columns.",
        (
            "the heading remains separate raw text above both columns",
            "layout analysis proposes the heading before column flow",
            "the source is wholly synthetic geometry evidence",
        ),
        _spanning_heading,
    ),
    FixtureCase(
        "footnote-layout",
        "Main flow followed by separated text near the page bottom.",
        (
            "main and bottom text remain separate raw blocks",
            "layout analysis proposes supported bottom text after main flow",
            "footnote status is only a geometry hypothesis",
        ),
        _footnote,
    ),
    FixtureCase(
        "sidebar-layout",
        "A narrow side group concurrent with wider main text.",
        (
            "main and side text remain separate raw blocks",
            "layout analysis exposes an uncertain sidebar hypothesis",
            "no confident sidebar insertion point is asserted",
        ),
        _sidebar,
    ),
    FixtureCase(
        "ambiguous-overlap",
        "Two weakly separated text blocks with no safe geometric order.",
        (
            "weakly separated raw text blocks remain available",
            "layout analysis reports explicit ordering ambiguity",
            "the fallback order carries low heuristic confidence",
        ),
        _ambiguous_overlap,
    ),
    FixtureCase(
        "equations",
        "Raw native text and geometry near a synthetic displayed equation.",
        (
            "the literal equation characters and source order are retained",
            "the display line has a distinct source bounding box",
            "no equation understanding or transcription quality is asserted",
        ),
        _equations,
    ),
    FixtureCase(
        "tables",
        "Raw positioned text evidence in a synthetic ruled table.",
        (
            "header and cell text blocks remain in extractor-native order",
            "cell block coordinates retain row and column positioning",
            "no table structure reconstruction is asserted",
        ),
        _tables,
    ),
    FixtureCase(
        "figures",
        "Embedded synthetic image reference plus native caption text.",
        (
            "an image/png content-addressed asset and geometry are retained",
            "caption text remains an independent raw text block",
            "no figure-caption association or figure semantics is asserted",
        ),
        _figures,
    ),
    FixtureCase(
        "printed-page-labels",
        "Physical page order with non-decimal printed page labels.",
        (
            "two physical pages remain ordered by zero-based page_index",
            "printed labels App-A and App-B are retained",
            "each text span repeats its containing page label",
        ),
        _page_labels,
    ),
    FixtureCase(
        "blank-page",
        "A deliberately blank physical page.",
        (
            "the blank physical page is not dropped",
            "the page has no extracted blocks",
            "pdf.low_text_density records a zero character count",
        ),
        _blank_page,
    ),
    FixtureCase(
        "image-only-page",
        "A synthetic image-only page without a native text layer.",
        (
            "the page contains an image reference and no text block",
            "image media type, asset identity, and geometry are retained",
            "pdf.low_text_density records a zero character count",
        ),
        _image_only,
    ),
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _round(value: float) -> float:
    return round(value, 4)


def project_result(fixture_id: str, payload: bytes) -> dict[str, object]:
    source = SourceDocument.from_bytes(
        payload,
        source_id=f"fixture:{fixture_id}",
        media_type="application/pdf",
        locator=f"tests/fixtures/pdf/{fixture_id}.pdf",
    )
    result = PyMuPdfExtractor().extract(source, BytesIO(payload))
    warnings_by_id = {
        warning.warning_id: warning for warning in result.warnings
    }
    associated_warning_ids: list[str] = []

    pages: list[dict[str, object]] = []
    for page in result.document.pages:
        page_warnings: list[dict[str, object]] = []
        for warning_id in page.warning_ids:
            warning = warnings_by_id.get(warning_id)
            if warning is None:
                raise RuntimeError(
                    f"page {page.page_index} refers to unknown warning "
                    f"{warning_id}"
                )
            if not any(
                span.page_index == page.page_index
                for span in warning.source_spans
            ):
                raise RuntimeError(
                    f"warning {warning_id} does not identify its associated "
                    f"page {page.page_index}"
                )
            associated_warning_ids.append(warning_id)
            page_warnings.append(
                {
                    "code": warning.code,
                    "severity": warning.severity.value,
                    "evidence": dict(warning.evidence),
                }
            )
        blocks: list[dict[str, object]] = []
        for block in page.blocks:
            span = block.source_spans[0]
            blocks.append(
                {
                    "kind": block.kind,
                    "text": block.text,
                    "asset_id": block.asset_id,
                    "asset_media_type": block.asset_media_type,
                    "extraction_method": block.extraction_method,
                    "confidence": block.confidence,
                    "source_object_id": span.source_object_id,
                    "printed_page_label": span.printed_page_label,
                    "bounding_box": (
                        [_round(value) for value in span.bounding_box]
                        if span.bounding_box is not None
                        else None
                    ),
                }
            )
        pages.append(
            {
                "page_index": page.page_index,
                "printed_page_label": page.printed_page_label,
                "width": _round(page.width),
                "height": _round(page.height),
                "coordinate_system": page.coordinate_system,
                "rotation_degrees": page.rotation_degrees,
                "extraction_quality": _round(page.extraction_quality),
                "blocks": blocks,
                "warnings": page_warnings,
            }
        )
    if sorted(associated_warning_ids) != sorted(warnings_by_id):
        raise RuntimeError(
            "result warnings and ExtractedPage.warning_ids do not agree"
        )
    return {
        "schema_version": 1,
        "fixture": fixture_id,
        "source_id": source.source_id,
        "source_sha256": source.content_hash,
        "pages": pages,
    }


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _pdf_bytes(case: FixtureCase, pymupdf: Any) -> bytes:
    document = case.build(pymupdf)
    try:
        return document.tobytes(
            garbage=4,
            deflate=True,
            no_new_id=True,
            reproducible=True,
        )
    finally:
        document.close()


def refresh() -> None:
    import pymupdf

    FIXTURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    fixtures: list[dict[str, object]] = []
    for case in CASES:
        pdf_path = FIXTURE_DIRECTORY / f"{case.fixture_id}.pdf"
        expected_path = FIXTURE_DIRECTORY / f"{case.fixture_id}.expected.json"
        payload = _pdf_bytes(case, pymupdf)
        expected = _json_bytes(project_result(case.fixture_id, payload))
        pdf_path.write_bytes(payload)
        expected_path.write_bytes(expected)
        rights = {
            "license": "Apache-2.0",
            "license_file": "LICENSE",
            "copyright": "Copyright (c) 2026 Eugene Ragasa",
        }
        fixtures.append(
            {
                "id": case.fixture_id,
                "purpose": case.purpose,
                "source": {
                    "path": str(pdf_path.relative_to(ROOT)),
                    "bytes": len(payload),
                    "sha256": _sha256(payload),
                    "provenance": (
                        "Wholly synthetic content generated by "
                        f"scripts/pdf_fixture_matrix.py:{case.build.__name__}; "
                        "no external document or layout was copied."
                    ),
                    "rights": rights,
                },
                "expected_output": {
                    "path": str(expected_path.relative_to(ROOT)),
                    "bytes": len(expected),
                    "sha256": _sha256(expected),
                    "provenance": (
                        "Focused deterministic cold-extraction projection "
                        "generated by scripts/pdf_fixture_matrix.py; run "
                        "timestamps and backend-derived identities are omitted."
                    ),
                    "rights": rights,
                },
                "assertions": list(case.assertions),
            }
        )
    manifest = {
        "schema_version": 1,
        "matrix_task": "ING-QUALITY-01",
        "generation": {
            "script": "scripts/pdf_fixture_matrix.py",
            "script_sha256": _sha256(SCRIPT_PATH.read_bytes()),
            "pymupdf_version": str(pymupdf.__version__),
            "policy": (
                "Committed PDFs are canonical exact-byte fixtures. Refresh is "
                "version-sensitive and must be reviewed; verification does not "
                "replace committed sources with freshly generated bytes."
            ),
        },
        "fixtures": fixtures,
    }
    MANIFEST_PATH.write_bytes(_json_bytes(manifest))
    print(f"refreshed {len(CASES)} fixtures with PyMuPDF {pymupdf.__version__}")


def verify() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    generation = manifest.get("generation", {})
    current_script_hash = _sha256(SCRIPT_PATH.read_bytes())
    if generation.get("script") != str(SCRIPT_PATH.relative_to(ROOT)):
        raise RuntimeError("manifest generation script path is stale")
    if generation.get("script_sha256") != current_script_hash:
        raise RuntimeError(
            "manifest generator SHA-256 is stale; run --refresh and review "
            "all regenerated fixture changes"
        )
    entries = manifest.get("fixtures", [])
    expected_ids = [case.fixture_id for case in CASES]
    actual_ids = [entry.get("id") for entry in entries]
    if actual_ids != expected_ids:
        raise RuntimeError(
            f"manifest fixture IDs differ: {actual_ids!r} != {expected_ids!r}"
        )

    for case, entry in zip(CASES, entries, strict=True):
        if entry.get("purpose") != case.purpose:
            raise RuntimeError(f"{case.fixture_id}: manifest purpose is stale")
        if entry.get("assertions") != list(case.assertions):
            raise RuntimeError(
                f"{case.fixture_id}: manifest assertions are stale"
            )
        source_contract = entry["source"]
        expected_contract = entry["expected_output"]
        source_path = ROOT / source_contract["path"]
        expected_path = ROOT / expected_contract["path"]
        payload = source_path.read_bytes()
        expected_bytes = expected_path.read_bytes()
        checks = (
            (len(payload), source_contract["bytes"], "source byte length"),
            (_sha256(payload), source_contract["sha256"], "source SHA-256"),
            (
                len(expected_bytes),
                expected_contract["bytes"],
                "expected-output byte length",
            ),
            (
                _sha256(expected_bytes),
                expected_contract["sha256"],
                "expected-output SHA-256",
            ),
        )
        for actual, recorded, label in checks:
            if actual != recorded:
                raise RuntimeError(
                    f"{case.fixture_id}: {label} differs: "
                    f"{actual!r} != {recorded!r}"
                )
        maintained = json.loads(expected_bytes)
        observed = project_result(case.fixture_id, payload)
        if observed != maintained:
            raise RuntimeError(
                f"{case.fixture_id}: cold extraction differs from maintained "
                "expected output; inspect the backend/adapter change and use "
                "--refresh only if the new evidence is intended"
            )
    print(
        f"verified {len(CASES)} fixture/source/output hash and extraction pairs"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--verify",
        action="store_true",
        help="verify committed hashes and focused extraction outputs",
    )
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="deliberately regenerate all PDFs, outputs, and hashes",
    )
    arguments = parser.parse_args()
    if arguments.refresh:
        refresh()
    else:
        verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
