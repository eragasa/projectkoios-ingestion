"""Deterministic page composition for recognition-independent transcripts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ReadingTranscriptPage:
    """One canonical reading page with separated text and visual evidence."""

    reading_page_id: str
    canonical_bytes: bytes
    selected_source: Literal["native", "ocr"]
    native_text_utf8_bytes: int
    selected_ocr_text_utf8_bytes: int
    visual_evidence_count: int

    @classmethod
    def compose(
        cls,
        *,
        book: str,
        source_sha256: str,
        page_index: int,
        native_page: Mapping[str, object],
        composed_page: Mapping[str, object],
        visual_evidence: list[dict[str, object]],
    ) -> ReadingTranscriptPage:
        """Compose one page without replacing or merging text streams."""

        if type(book) is not str or not book:
            raise ValueError("reading page book is required")
        if (
            type(source_sha256) is not str
            or len(source_sha256) != 64
            or any(value not in "0123456789abcdef" for value in source_sha256)
        ):
            raise ValueError("reading page source hash must be SHA-256")
        if type(page_index) is not int or page_index < 0:
            raise ValueError("reading page index must be nonnegative")
        if type(native_page) is not dict or type(composed_page) is not dict:
            raise TypeError("reading page text evidence must be dicts")
        if type(visual_evidence) is not list or any(
            type(value) is not dict for value in visual_evidence
        ):
            raise TypeError("reading page visual evidence must be a dict list")

        native_text = native_page.get("text")
        native_sha256 = native_page.get("text_sha256")
        native_byte_size = native_page.get("text_utf8_byte_length")
        page_id = native_page.get("page_id")
        if (
            type(native_text) is not str
            or type(native_sha256) is not str
            or type(native_byte_size) is not int
            or type(page_id) is not str
            or not page_id
        ):
            raise ValueError("native page evidence is incomplete")
        native_payload = native_text.encode()
        if (
            hashlib.sha256(native_payload).hexdigest() != native_sha256
            or len(native_payload) != native_byte_size
        ):
            raise ValueError("native page text evidence differs")

        chosen = composed_page.get("chosen_source")
        selected_ocr: dict[str, object] | None
        reading_selection: str
        selected_ocr_byte_size = 0
        if chosen == "native":
            if composed_page.get("text") != native_text:
                raise ValueError("composed native text differs")
            selected_ocr = None
            reading_selection = "native_text"
            selected_source: Literal["native", "ocr"] = "native"
        elif chosen == "ocr":
            ocr_text = composed_page.get("text")
            ocr_sha256 = composed_page.get("text_sha256")
            ocr_byte_size = composed_page.get("text_utf8_byte_length")
            composition_id = composed_page.get("composition_id")
            if (
                type(ocr_text) is not str
                or type(ocr_sha256) is not str
                or type(ocr_byte_size) is not int
                or type(composition_id) is not str
                or not composition_id
            ):
                raise ValueError("selected OCR evidence is incomplete")
            ocr_payload = ocr_text.encode()
            if (
                hashlib.sha256(ocr_payload).hexdigest() != ocr_sha256
                or len(ocr_payload) != ocr_byte_size
            ):
                raise ValueError("selected OCR text evidence differs")
            selected_ocr_byte_size = len(ocr_payload)
            selected_ocr = {
                "composition_id": composition_id,
                "text": ocr_text,
                "text_sha256": ocr_sha256,
                "text_utf8_byte_length": ocr_byte_size,
                "automated": True,
                "accepted": False,
            }
            reading_selection = "selected_ocr_text"
            selected_source = "ocr"
        else:
            raise ValueError("composed page text source is unsupported")

        copied_visuals = [
            json.loads(cls._canonical(value)) for value in visual_evidence
        ]
        copied_visuals.sort(
            key=lambda value: (
                *cls._evidence_position(value),
                str(value["evidence_type"]),
                str(value.get("assembly_id", value.get("candidate_id"))),
            )
        )
        for order, value in enumerate(copied_visuals):
            value["visual_order"] = order
        page_body = {
            "contract_version": "1.0",
            "book": book,
            "source_sha256": source_sha256,
            "page_index": page_index,
            "physical_page": page_index + 1,
            "printed_page_label": composed_page.get("printed_page_label"),
            "text_evidence": {
                "native_text": {
                    "page_id": page_id,
                    "text": native_text,
                    "text_sha256": native_sha256,
                    "text_utf8_byte_length": native_byte_size,
                },
                "selected_ocr_text": selected_ocr,
                "reading_selection": reading_selection,
                "chunking_status": "not_requested",
            },
            "visual_evidence": copied_visuals,
        }
        reading_page_id = cls._identity(
            "reference-reading-transcript-page", page_body
        )
        page = {**page_body, "reading_page_id": reading_page_id}
        canonical_bytes = cls._canonical(page)
        return cls(
            reading_page_id=reading_page_id,
            canonical_bytes=canonical_bytes,
            selected_source=selected_source,
            native_text_utf8_bytes=len(native_payload),
            selected_ocr_text_utf8_bytes=selected_ocr_byte_size,
            visual_evidence_count=len(copied_visuals),
        )

    def to_record(self) -> dict[str, object]:
        """Return a detached mutable representation of the canonical page."""

        value = json.loads(self.canonical_bytes)
        if type(value) is not dict:
            raise RuntimeError("canonical reading page is not an object")
        return value

    def __post_init__(self) -> None:
        if type(self.canonical_bytes) is not bytes or not self.canonical_bytes:
            raise ValueError("canonical reading page bytes are required")
        value = json.loads(self.canonical_bytes)
        if type(value) is not dict:
            raise ValueError("canonical reading page must be an object")
        if self.canonical_bytes != self._canonical(value):
            raise ValueError("reading page bytes are not canonical")
        body = dict(value)
        observed = body.pop("reading_page_id", None)
        expected = self._identity("reference-reading-transcript-page", body)
        if observed != self.reading_page_id or observed != expected:
            raise ValueError("reading page identity differs")
        if self.selected_source not in ("native", "ocr"):
            raise ValueError("reading page selected source is invalid")
        text = value.get("text_evidence")
        if type(text) is not dict:
            raise ValueError("reading page text evidence is invalid")
        expected_selection = (
            "native_text"
            if self.selected_source == "native"
            else "selected_ocr_text"
        )
        if (
            text.get("reading_selection") != expected_selection
            or text.get("chunking_status") != "not_requested"
        ):
            raise ValueError("reading page text selection differs")
        native = text.get("native_text")
        if type(native) is not dict or type(native.get("text")) is not str:
            raise ValueError("reading page native text is invalid")
        native_payload = native["text"].encode()
        if (
            hashlib.sha256(native_payload).hexdigest()
            != native.get("text_sha256")
            or len(native_payload) != native.get("text_utf8_byte_length")
            or len(native_payload) != self.native_text_utf8_bytes
        ):
            raise ValueError("reading page native text bytes differ")
        selected_ocr = text.get("selected_ocr_text")
        if self.selected_source == "native":
            if selected_ocr is not None or self.selected_ocr_text_utf8_bytes:
                raise ValueError("native selection contains OCR evidence")
        else:
            if (
                type(selected_ocr) is not dict
                or type(selected_ocr.get("text")) is not str
                or selected_ocr.get("accepted") is not False
            ):
                raise ValueError("selected OCR evidence is invalid")
            ocr_payload = selected_ocr["text"].encode()
            if (
                hashlib.sha256(ocr_payload).hexdigest()
                != selected_ocr.get("text_sha256")
                or len(ocr_payload) != selected_ocr.get("text_utf8_byte_length")
                or len(ocr_payload) != self.selected_ocr_text_utf8_bytes
            ):
                raise ValueError("selected OCR evidence bytes differ")
        visuals = value.get("visual_evidence")
        if (
            type(visuals) is not list
            or any(type(item) is not dict for item in visuals)
            or len(visuals) != self.visual_evidence_count
        ):
            raise ValueError("reading page visual coverage differs")
        if [item.get("visual_order") for item in visuals] != list(
            range(len(visuals))
        ):
            raise ValueError("reading page visual order differs")

    @staticmethod
    def _canonical(value: object) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

    @classmethod
    def _identity(cls, namespace: str, value: object) -> str:
        return (
            f"{namespace}:sha256:"
            f"{hashlib.sha256(cls._canonical(value)).hexdigest()}"
        )

    @staticmethod
    def _evidence_position(value: dict[str, object]) -> tuple[float, float]:
        spans = value.get("source_spans", [])
        if type(spans) is not list:
            raise ValueError("visual evidence source spans must be a list")
        boxes = [
            span["bounding_box"]
            for span in spans
            if type(span) is dict and span.get("bounding_box") is not None
        ]
        if not boxes:
            return (float("inf"), float("inf"))
        if any(
            type(box) is not list
            or len(box) != 4
            or any(
                isinstance(coordinate, bool)
                or not isinstance(coordinate, (int, float))
                for coordinate in box
            )
            for box in boxes
        ):
            raise ValueError("visual evidence bounding box is invalid")
        return (
            min(float(box[1]) for box in boxes),
            min(float(box[0]) for box in boxes),
        )
