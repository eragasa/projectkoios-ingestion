from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import pdf_fixture_matrix

pymupdf = pytest.importorskip("pymupdf")

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = ROOT / "tests" / "fixtures" / "pdf"


def _observe(fixture_id: str) -> dict[str, Any]:
    payload = (FIXTURE_DIRECTORY / f"{fixture_id}.pdf").read_bytes()
    return pdf_fixture_matrix.project_result(fixture_id, payload)


def test__pdf_fixture_matrix__manifest_integrity_and_expected_outputs() -> None:
    manifest = json.loads((FIXTURE_DIRECTORY / "manifest.json").read_text())

    assert manifest["matrix_task"] == "ING-QUALITY-01"
    script_bytes = pdf_fixture_matrix.SCRIPT_PATH.read_bytes()
    assert (
        manifest["generation"]["script_sha256"]
        == hashlib.sha256(script_bytes).hexdigest()
    )
    assert [entry["id"] for entry in manifest["fixtures"]] == [
        case.fixture_id for case in pdf_fixture_matrix.CASES
    ]
    for case, entry in zip(
        pdf_fixture_matrix.CASES, manifest["fixtures"], strict=True
    ):
        source = entry["source"]
        expected_output = entry["expected_output"]
        source_bytes = (ROOT / source["path"]).read_bytes()
        expected_bytes = (ROOT / expected_output["path"]).read_bytes()

        rights = {
            "copyright": "Copyright (c) 2026 Eugene Ragasa",
            "license": "MIT",
            "license_file": "LICENSE",
        }
        assert source["rights"] == rights
        assert expected_output["rights"] == rights
        assert "Wholly synthetic" in source["provenance"]
        assert "deterministic cold-extraction" in expected_output["provenance"]
        assert entry["purpose"] == case.purpose
        assert entry["assertions"] == list(case.assertions)
        assert len(source_bytes) == source["bytes"]
        assert hashlib.sha256(source_bytes).hexdigest() == source["sha256"]
        assert len(expected_bytes) == expected_output["bytes"]
        assert (
            hashlib.sha256(expected_bytes).hexdigest()
            == expected_output["sha256"]
        )
        assert _observe(entry["id"]) == json.loads(expected_bytes)


def test__pdf_fixture_matrix__born_digital_text() -> None:
    page = _observe("born-digital-text")["pages"][0]
    block = page["blocks"][0]

    assert block["text"] == (
        "Born-digital text evidence\nAlpha beta gamma delta\n"
        "Native text remains raw extraction evidence."
    )
    assert block["kind"] == "text"
    assert block["bounding_box"] == [54.0, 54.0, 269.798, 101.6091]
    assert 0.0 < page["extraction_quality"] < 1.0
    assert page["rotation_degrees"] == 0
    assert page["warnings"] == []


def test__pdf_fixture_matrix__two_column_native_order_without_warning() -> None:
    page = _observe("two-column-layout")["pages"][0]
    right, left = page["blocks"]

    assert right["text"].startswith("RIGHT COLUMN FIRST")
    assert left["text"].startswith("LEFT COLUMN SECOND")
    assert right["bounding_box"][0] > left["bounding_box"][2]
    assert page["warnings"] == []


def test__pdf_fixture_matrix__equation_raw_text_and_geometry() -> None:
    page = _observe("equations")["pages"][0]
    heading, equation, disclaimer = page["blocks"]

    assert equation["text"] == "E = m c^2    (1)"
    assert heading["bounding_box"][1] < equation["bounding_box"][1]
    assert equation["bounding_box"][3] < disclaimer["bounding_box"][1]
    assert {block["kind"] for block in page["blocks"]} == {"text"}
    assert page["warnings"] == []


def test__pdf_fixture_matrix__table_raw_cell_order_and_geometry() -> None:
    page = _observe("tables")["pages"][0]
    title, header_a, header_b, cell_a, cell_b = page["blocks"]

    assert [block["text"] for block in page["blocks"]] == [
        "Table evidence: positioned native text",
        "Header A\ncolumn one",
        "Header B\ncolumn two",
        "Cell A1\nrow one",
        "Cell B1\nrow one",
    ]
    assert header_a["bounding_box"][0] < header_b["bounding_box"][0]
    assert header_a["bounding_box"][1] == header_b["bounding_box"][1]
    assert cell_a["bounding_box"][0] < cell_b["bounding_box"][0]
    assert header_a["bounding_box"][3] < cell_a["bounding_box"][1]
    assert title["kind"] == "text"
    assert page["warnings"] == []


def test__pdf_fixture_matrix__figure_image_reference_and_caption() -> None:
    page = _observe("figures")["pages"][0]
    image, caption = page["blocks"]

    assert (image["kind"], caption["kind"]) == ("image", "text")
    assert image["asset_media_type"] == "image/png"
    assert image["asset_id"].startswith("asset:sha256:")
    assert image["bounding_box"] == [90.0, 55.0, 330.0, 215.0]
    assert caption["text"] == "Figure 1. Synthetic blue rectangle caption."
    assert image["bounding_box"][3] < caption["bounding_box"][1]


def test__pdf_fixture_matrix__image_sources_have_no_icc_profile() -> None:
    for fixture_id in ("figures", "image-only-page"):
        payload = (FIXTURE_DIRECTORY / f"{fixture_id}.pdf").read_bytes()
        assert b"/ICCBased" not in payload
        with pymupdf.open(stream=payload, filetype="pdf") as document:
            images = document.get_page_images(0, full=True)
            assert len(images) == 1
            assert document.xref_get_key(images[0][0], "ColorSpace") == (
                "name",
                "/DeviceRGB",
            )


def test__pdf_fixture_matrix__printed_page_and_span_labels() -> None:
    pages = _observe("printed-page-labels")["pages"]

    assert [page["page_index"] for page in pages] == [0, 1]
    assert [page["printed_page_label"] for page in pages] == [
        "App-A",
        "App-B",
    ]
    assert [page["blocks"][0]["printed_page_label"] for page in pages] == [
        "App-A",
        "App-B",
    ]


def test__pdf_fixture_matrix__blank_page_warning() -> None:
    page = _observe("blank-page")["pages"][0]

    assert page["page_index"] == 0
    assert page["extraction_quality"] == 0.0
    assert page["blocks"] == []
    assert page["warnings"] == [
        {
            "code": "pdf.low_text_density",
            "evidence": {"character_count": "0"},
            "severity": "warning",
        }
    ]


def test__pdf_fixture_matrix__image_only_page_warning_and_geometry() -> None:
    page = _observe("image-only-page")["pages"][0]
    image = page["blocks"][0]

    assert [block["kind"] for block in page["blocks"]] == ["image"]
    assert page["extraction_quality"] == 0.0
    assert image["text"] is None
    assert image["asset_media_type"] == "image/png"
    assert image["asset_id"].startswith("asset:sha256:")
    assert image["bounding_box"] == [72.0, 54.0, 348.0, 246.0]
    assert page["warnings"] == [
        {
            "code": "pdf.low_text_density",
            "evidence": {"character_count": "0"},
            "severity": "warning",
        }
    ]
