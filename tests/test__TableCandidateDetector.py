from __future__ import annotations

from collections.abc import Iterable
from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, cast

import pytest
from projectkoios.ingestion import (
    DeterministicLayoutProcessor,
    DeterministicTableCandidateDetector,
    PageRegionSelection,
    PyMuPdfExtractor,
    RenderedRegion,
    SourceDocument,
    TableAssociationRole,
    TableBoundaryKind,
    TableCandidateDetector,
    TableDetectionConfiguration,
    TableDetectionLimitError,
    TableDetectionResult,
    TableEvidenceStatus,
)

pymupdf = pytest.importorskip("pymupdf")


def _source(payload: bytes, suffix: str) -> SourceDocument:
    return SourceDocument.from_bytes(
        payload,
        source_id=f"article:table:{suffix}",
        media_type="application/pdf",
        locator=f"memory://table-{suffix}.pdf",
    )


def _add_table(
    page: Any,
    *,
    title: str | None,
    y: float = 90.0,
    ruled: bool = False,
    merged: bool = False,
    caption: str | None = None,
    note: str | None = None,
    long_text: bool = False,
) -> None:
    if title is not None:
        page.insert_text((50, y - 35), title, fontsize=11)
    if merged:
        page.insert_textbox(
            (185, y, 350, y + 30),
            "Merged heading",
            fontsize=10,
        )
        first_row = y + 45
    else:
        first_row = y
    boxes = (
        (50, first_row, 210, first_row + 40),
        (310, first_row, 470, first_row + 40),
        (50, first_row + 55, 210, first_row + 95),
        (310, first_row + 55, 470, first_row + 95),
    )
    values = (
        (
            "Descriptive words here\nleft one",
            "Descriptive words here\nright one",
            "Descriptive words here\nleft two",
            "Descriptive words here\nright two",
        )
        if long_text
        else (
            "Header A\ncolumn one",
            "Header B\ncolumn two",
            "Cell A1\nrow one",
            "Cell B1\nrow one",
        )
    )
    for box, value in zip(boxes, values, strict=True):
        page.insert_textbox(box, value, fontsize=10)
    table_bottom = first_row + 95
    if ruled:
        left = 44
        middle = 270
        right = 466
        top = y - 5 if merged else first_row - 5
        for x in (left, right):
            page.draw_line((x, top), (x, table_bottom), width=0.5)
        page.draw_line(
            (middle, first_row - 5), (middle, table_bottom), width=0.5
        )
        for line_y in (top, first_row + 40, table_bottom):
            page.draw_line((left, line_y), (right, line_y), width=0.5)
    next_y = table_bottom + 28
    if caption is not None:
        page.insert_text((50, next_y), caption, fontsize=10)
        next_y += 24
    if note is not None:
        page.insert_text((50, next_y), note, fontsize=10)


def _pdf(
    page_specs: tuple[dict[str, object], ...],
    *,
    rotation: int = 0,
) -> bytes:
    document = pymupdf.open()
    for spec in page_specs:
        page = document.new_page(width=520, height=420)
        _add_table(page, **cast(Any, spec))
        if rotation:
            page.set_rotation(rotation)
    payload = document.tobytes()
    document.close()
    return payload


def _extract(payload: bytes, suffix: str):
    source = _source(payload, suffix)
    document = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    return source, document


def _detect(
    payload: bytes,
    suffix: str,
    configuration: TableDetectionConfiguration | None = None,
) -> TableDetectionResult:
    _, document = _extract(payload, suffix)
    return DeterministicTableCandidateDetector(configuration).detect(
        document, BytesIO(payload)
    )


def test__table_detector__detects_maintained_ruled_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "tables.pdf"
    result = _detect(fixture.read_bytes(), "fixture")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.boundary_kind is TableBoundaryKind.RULED
    assert candidate.evidence_status is TableEvidenceStatus.PROPOSED
    assert candidate.warning_ids == ()
    assert len(candidate.regions) == 1
    region = candidate.regions[0]
    assert region.row_band_count == 2
    assert region.column_band_count == 2
    assert len(region.rule_segment_ids) == 6
    assert (
        result.detection_input.page_rule_evidence[0].ignored_drawing_item_count
        == 0
    )
    assert len(region.block_ids) == 4
    assert region.rendered_region.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert region.rendered_region.selection_was_full_page is False
    assert tuple(item.role for item in candidate.associations) == (
        TableAssociationRole.TITLE,
    )
    assert candidate.associations[0].text == (
        "Table evidence: positioned native text"
    )


def test__table_detector__rejects_other_maintained_pdf_shapes() -> None:
    fixture_directory = Path(__file__).parent / "fixtures" / "pdf"
    detected: dict[str, int] = {}
    for fixture in sorted(fixture_directory.glob("*.pdf")):
        result = _detect(fixture.read_bytes(), f"matrix-{fixture.stem}")
        detected[fixture.stem] = len(result.candidates)

    assert detected["tables"] == 1
    assert all(
        count == 0 for name, count in detected.items() if name != "tables"
    )


def test__table_detector__detects_unruled_associations() -> None:
    payload = _pdf(
        (
            {
                "title": "Table 2. Synthetic measurements",
                "caption": "Caption: bounded synthetic values",
                "note": "Note: no scientific claim is made",
            },
        )
    )

    result = _detect(payload, "unruled")

    candidate = result.candidates[0]
    assert candidate.boundary_kind is TableBoundaryKind.UNRULED
    assert candidate.evidence_status is TableEvidenceStatus.PROPOSED
    assert candidate.source_label == "Table 2"
    assert tuple(item.role for item in candidate.associations) == (
        TableAssociationRole.TITLE,
        TableAssociationRole.CAPTION,
        TableAssociationRole.NOTE,
    )
    assert candidate.warning_ids == ()


def test__table_detector__links_explicit_multi_page_continuation() -> None:
    payload = _pdf(
        (
            {"title": "Table 3. First page", "ruled": True},
            {"title": "Table 3 (continued)", "ruled": True},
        )
    )

    result = _detect(payload, "multi-page")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.source_label == "Table 3"
    assert tuple(region.page_index for region in candidate.regions) == (0, 1)
    assert any(
        association.role is TableAssociationRole.CONTINUATION_LABEL
        for association in candidate.associations
    )
    assert all(region.rendered_region.content for region in candidate.regions)


def test__table_detector__preserves_merged_cell_signal_as_warning() -> None:
    payload = _pdf(
        (
            {
                "title": "Table 4. Merged heading evidence",
                "ruled": True,
                "merged": True,
            },
        )
    )

    result = _detect(payload, "merged")

    candidate = result.candidates[0]
    region = candidate.regions[0]
    assert region.row_band_count == 3
    assert region.merged_cell_signal_block_ids
    assert candidate.warning_ids
    assert any(
        warning.code == "table.merged_cell_signal"
        and candidate.candidate_id in warning.object_ids
        for warning in result.warnings
    )


def test__table_detector__marks_prose_like_candidate_ambiguous() -> None:
    payload = _pdf(
        (
            {
                "title": None,
                "long_text": True,
            },
        )
    )
    configuration = TableDetectionConfiguration(prose_character_threshold=20)

    result = _detect(payload, "ambiguous", configuration)

    candidate = result.candidates[0]
    assert candidate.evidence_status is TableEvidenceStatus.AMBIGUOUS
    assert {warning.code for warning in result.warnings} == {
        "table.ambiguous_candidate",
        "table.prose_like_candidate",
    }
    assert candidate.warning_ids


def test__table_detector__renders_rotated_page_evidence() -> None:
    payload = _pdf(
        ({"title": "Table 5. Rotated", "ruled": True},),
        rotation=90,
    )

    result = _detect(payload, "rotated")

    assert (
        result.candidates[0].regions[0].rendered_region.page_rotation_degrees
        == 90
    )


def test__table_detector__rejects_stale_layout() -> None:
    payload = _pdf(({"title": "Table 6. Current"},))
    _, document = _extract(payload, "current")
    other_payload = _pdf(({"title": "Table 7. Other"},))
    _, other = _extract(other_payload, "other")
    stale = DeterministicLayoutProcessor().analyze(other)

    with pytest.raises(ValueError, match="does not match"):
        DeterministicTableCandidateDetector().detect_with_layout(
            document, BytesIO(payload), stale
        )


def test__table_detector__requires_exact_pdf_bytes() -> None:
    payload = _pdf(({"title": "Table 8. Exact", "ruled": True},))
    _, document = _extract(payload, "exact")

    with pytest.raises(ValueError, match="source bytes"):
        DeterministicTableCandidateDetector().detect(
            document, BytesIO(b"not the source PDF")
        )


def test__table_detector__enforces_candidate_limit_before_rendering() -> None:
    payload = _pdf(
        (
            {
                "title": "Table 9. First",
                "y": 70.0,
            },
        )
    )
    # Add a second distant table to the same page while keeping exact PDF input.
    document = pymupdf.open(stream=payload, filetype="pdf")
    page = document[0]
    _add_table(page, title=None, y=280.0)
    payload = document.tobytes()
    document.close()

    class RejectingRenderer:
        def render(
            self,
            source: SourceDocument,
            content: BinaryIO,
            selections: Iterable[PageRegionSelection],
        ) -> tuple[RenderedRegion, ...]:
            raise AssertionError("renderer must not run after candidate limit")

    _, extracted = _extract(payload, "candidate-limit")
    detector = DeterministicTableCandidateDetector(
        TableDetectionConfiguration(max_candidates=1),
        region_renderer=RejectingRenderer(),
    )
    with pytest.raises(TableDetectionLimitError, match="max_candidates"):
        detector.detect(extracted, BytesIO(payload))


def test__table_detector__enforces_rendered_aggregate_limit() -> None:
    payload = _pdf(({"title": "Table 11. Render limit", "ruled": True},))

    with pytest.raises(
        TableDetectionLimitError, match="max_total_rendered_pixels"
    ):
        _detect(
            payload,
            "render-limit",
            TableDetectionConfiguration(max_total_rendered_pixels=1),
        )


def test__table_detector__is_deterministic_immutable_and_protocol_typed() -> (
    None
):
    payload = _pdf(({"title": "Table 10. Stable", "ruled": True},))

    first = _detect(payload, "stable")
    second = _detect(payload, "stable")

    assert first == second
    assert first.result_id == second.result_id
    assert first.candidates[0].candidate_id == second.candidates[0].candidate_id
    detector: TableCandidateDetector = DeterministicTableCandidateDetector()
    assert detector.name == "deterministic-table-candidate-detector"
    with pytest.raises(FrozenInstanceError):
        first.result_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="result ID"):
        replace(first, result_id="changed")
    with pytest.raises(ValueError, match="candidate ID"):
        replace(first.candidates[0], candidate_id="changed")
