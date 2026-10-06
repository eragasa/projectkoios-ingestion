from __future__ import annotations

import pytest
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

from workflows.reading_transcript_page import ReadingTranscriptPage

SOURCE_SHA256 = "a" * 64


def native_page(text: str = "native page text") -> dict[str, object]:
    payload = text.encode()
    return {
        "page_id": "page:fixture",
        "text": text,
        "text_sha256": SHA256Fingerprinter.fingerprint(content=payload),
        "text_utf8_byte_length": len(payload),
    }


def composed_native(text: str = "native page text") -> dict[str, object]:
    payload = text.encode()
    return {
        "chosen_source": "native",
        "text": text,
        "text_sha256": SHA256Fingerprinter.fingerprint(content=payload),
        "text_utf8_byte_length": len(payload),
        "printed_page_label": "7",
    }


def visual(
    *, evidence_type: str, identity: str, x: float, y: float
) -> dict[str, object]:
    key = "assembly_id" if evidence_type == "equation" else "candidate_id"
    return {
        "evidence_type": evidence_type,
        key: identity,
        "source_spans": [
            {"page_index": 0, "bounding_box": [x, y, x + 1.0, y + 1.0]}
        ],
    }


def test__reading_page__orders_visuals_and_derives_identity() -> None:
    lower = visual(
        evidence_type="figure",
        identity="figure:lower",
        x=1.0,
        y=20.0,
    )
    upper = visual(
        evidence_type="equation",
        identity="equation:upper",
        x=5.0,
        y=10.0,
    )

    page = ReadingTranscriptPage.compose(
        book="Fixture",
        source_sha256=SOURCE_SHA256,
        page_index=0,
        native_page=native_page(),
        composed_page=composed_native(),
        visual_evidence=[lower, upper],
    )
    record = page.to_record()

    assert page.reading_page_id.startswith(
        "reference-reading-transcript-page:sha256:"
    )
    assert page.selected_source == "native"
    assert page.native_text_utf8_bytes == len(b"native page text")
    assert page.selected_ocr_text_utf8_bytes == 0
    assert [item["evidence_type"] for item in record["visual_evidence"]] == [
        "equation",
        "figure",
    ]
    assert [item["visual_order"] for item in record["visual_evidence"]] == [
        0,
        1,
    ]
    assert "visual_order" not in lower
    assert "visual_order" not in upper
    assert (
        ReadingTranscriptPage.compose(
            book="Fixture",
            source_sha256=SOURCE_SHA256,
            page_index=0,
            native_page=native_page(),
            composed_page=composed_native(),
            visual_evidence=[lower, upper],
        ).canonical_bytes
        == page.canonical_bytes
    )


def test__reading_page__retains_native_and_selected_ocr_separately() -> None:
    ocr_text = "selected OCR text"
    ocr_payload = ocr_text.encode()
    composed = {
        "chosen_source": "ocr",
        "composition_id": "composition:fixture",
        "text": ocr_text,
        "text_sha256": SHA256Fingerprinter.fingerprint(content=ocr_payload),
        "text_utf8_byte_length": len(ocr_payload),
        "printed_page_label": None,
    }

    page = ReadingTranscriptPage.compose(
        book="Fixture",
        source_sha256=SOURCE_SHA256,
        page_index=2,
        native_page=native_page(),
        composed_page=composed,
        visual_evidence=[],
    )
    record = page.to_record()
    text = record["text_evidence"]

    assert page.selected_source == "ocr"
    assert page.selected_ocr_text_utf8_bytes == len(ocr_payload)
    assert text["native_text"]["text"] == "native page text"
    assert text["selected_ocr_text"] == {
        "composition_id": "composition:fixture",
        "text": ocr_text,
        "text_sha256": SHA256Fingerprinter.fingerprint(content=ocr_payload),
        "text_utf8_byte_length": len(ocr_payload),
        "automated": True,
        "accepted": False,
    }
    assert text["reading_selection"] == "selected_ocr_text"
    assert text["chunking_status"] == "not_requested"


def test__reading_page__rejects_changed_native_text() -> None:
    composed = composed_native()
    composed["text"] = "replacement text"

    with pytest.raises(ValueError, match="composed native text"):
        ReadingTranscriptPage.compose(
            book="Fixture",
            source_sha256=SOURCE_SHA256,
            page_index=0,
            native_page=native_page(),
            composed_page=composed,
            visual_evidence=[],
        )


def test__reading_page__rejects_invalid_ocr_digest() -> None:
    composed = {
        "chosen_source": "ocr",
        "composition_id": "composition:fixture",
        "text": "OCR",
        "text_sha256": "0" * 64,
        "text_utf8_byte_length": 3,
        "printed_page_label": None,
    }

    with pytest.raises(ValueError, match="OCR text evidence differs"):
        ReadingTranscriptPage.compose(
            book="Fixture",
            source_sha256=SOURCE_SHA256,
            page_index=0,
            native_page=native_page(),
            composed_page=composed,
            visual_evidence=[],
        )
