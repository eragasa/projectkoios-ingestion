from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pytest
from projectkoios.ingestion import (
    DeterministicTableCandidateDetector,
    DeterministicTableStructureReconstructor,
    PyMuPdfExtractor,
    SourceDocument,
    TableCandidateDetector,
    TableCellRole,
    TableStructureConfiguration,
    TableStructureEvidenceStatus,
    TableStructureLimitError,
    TableStructureReconstructor,
)

pymupdf = pytest.importorskip("pymupdf")


def _source(payload: bytes, suffix: str) -> SourceDocument:
    return SourceDocument.from_bytes(
        payload,
        source_id=f"article:table-structure:{suffix}",
        media_type="application/pdf",
        locator=f"memory://table-structure-{suffix}.pdf",
    )


def _add_table(
    page: Any,
    *,
    title: str,
    ruled: bool = False,
    merged: bool = False,
    explicit_headers: bool = True,
) -> None:
    y = 90.0
    page.insert_text((50, y - 35), title, fontsize=11)
    if merged:
        page.insert_textbox(
            (185, y, 350, y + 30), "Merged heading", fontsize=10
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
            "Header A\ncolumn one",
            "Header B\ncolumn two",
            "Cell A1\nrow one",
            "Cell B1\nrow one",
        )
        if explicit_headers
        else (
            "Alpha words\ncolumn one",
            "Beta words\ncolumn two",
            "Gamma words\nrow one",
            "Delta words\nrow one",
        )
    )
    for box, value in zip(boxes, values, strict=True):
        page.insert_textbox(box, value, fontsize=10)
    if ruled:
        left, middle, right = 44, 270, 466
        top = y - 5 if merged else first_row - 5
        bottom = first_row + 95
        for x in (left, right):
            page.draw_line((x, top), (x, bottom), width=0.5)
        page.draw_line((middle, first_row - 5), (middle, bottom), width=0.5)
        for line_y in (top, first_row + 40, bottom):
            page.draw_line((left, line_y), (right, line_y), width=0.5)


def _pdf(page_specs: tuple[dict[str, object], ...]) -> bytes:
    document = pymupdf.open()
    for spec in page_specs:
        page = document.new_page(width=520, height=420)
        _add_table(page, **cast(Any, spec))
    payload = document.tobytes()
    document.close()
    return payload


def _detect(payload: bytes, suffix: str):
    source = _source(payload, suffix)
    document = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    detector: TableCandidateDetector = DeterministicTableCandidateDetector()
    return detector.detect(document, BytesIO(payload))


def test__table_structure__reconstructs_maintained_ruled_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "tables.pdf"
    detection = _detect(fixture.read_bytes(), "fixture")
    reconstructor: TableStructureReconstructor = (
        DeterministicTableStructureReconstructor()
    )

    result = reconstructor.reconstruct(detection)

    assert len(result.structures) == 1
    structure = result.structures[0]
    assert structure.evidence_status is TableStructureEvidenceStatus.PROPOSED
    assert len(structure.columns) == 2
    assert len(structure.rows) == 2
    assert len(structure.cells) == 4
    assert result.warnings == ()
    assert tuple(cell.role for cell in structure.cells) == (
        TableCellRole.HEADER,
        TableCellRole.HEADER,
        TableCellRole.BODY,
        TableCellRole.BODY,
    )
    assert tuple(cell.proposed_text for cell in structure.cells) == (
        "Header A\ncolumn one",
        "Header B\ncolumn two",
        "Cell A1\nrow one",
        "Cell B1\nrow one",
    )
    assert all(len(cell.source_block_ids) == 1 for cell in structure.cells)
    assert all(cell.source_spans for cell in structure.cells)
    assert all(cell.rendered_region_ids for cell in structure.cells)
    assert all(
        cell.text_join_method == "single_source_block_exact"
        for cell in structure.cells
    )
    assert structure.association_ids == tuple(
        association.association_id
        for association in detection.candidates[0].associations
    )


def test__table_structure__retains_unruled_uncertainty() -> None:
    payload = _pdf(
        (
            {
                "title": "Table 2. Synthetic measurements",
                "explicit_headers": False,
            },
        )
    )

    result = DeterministicTableStructureReconstructor().reconstruct(
        _detect(payload, "unruled")
    )

    structure = result.structures[0]
    assert structure.evidence_status is TableStructureEvidenceStatus.AMBIGUOUS
    assert all(cell.role is TableCellRole.UNKNOWN for cell in structure.cells)
    assert {warning.code for warning in result.warnings} == {
        "table_structure.header_unresolved",
        "table_structure.unruled_geometry",
    }
    assert structure.warning_ids == tuple(
        warning.warning_id for warning in result.warnings
    )


def test__table_structure__represents_merged_column_span_as_ambiguous() -> None:
    payload = _pdf(
        (
            {
                "title": "Table 4. Merged synthetic heading",
                "ruled": True,
                "merged": True,
            },
        )
    )

    result = DeterministicTableStructureReconstructor().reconstruct(
        _detect(payload, "merged")
    )

    structure = result.structures[0]
    merged = structure.cells[0]
    assert merged.proposed_text == "Merged heading"
    assert merged.column_index == 0
    assert merged.column_span == 2
    assert merged.row_span == 1
    assert merged.role is TableCellRole.UNKNOWN
    assert merged.evidence_status is TableStructureEvidenceStatus.AMBIGUOUS
    assert len(merged.warning_ids) == 1
    assert (
        next(
            warning
            for warning in result.warnings
            if warning.warning_id in merged.warning_ids
        ).code
        == "table_structure.merged_span_ambiguous"
    )
    assert tuple(cell.role for cell in structure.cells[1:3]) == (
        TableCellRole.HEADER,
        TableCellRole.HEADER,
    )


def test__table_structure__keeps_explicit_multi_page_rows_separate() -> None:
    payload = _pdf(
        (
            {"title": "Table 3. First page", "ruled": True},
            {"title": "Table 3 (continued)", "ruled": True},
        )
    )

    result = DeterministicTableStructureReconstructor().reconstruct(
        _detect(payload, "multi-page")
    )

    structure = result.structures[0]
    assert tuple(row.page_index for row in structure.rows) == (0, 0, 1, 1)
    assert tuple(row.reading_order for row in structure.rows) == (0, 1, 2, 3)
    assert tuple(row.repeated_header for row in structure.rows) == (
        False,
        False,
        True,
        False,
    )
    assert len(structure.cells) == 8
    assert len(structure.continuations) == 1
    continuation = structure.continuations[0]
    assert continuation.previous_page_index == 0
    assert continuation.current_page_index == 1
    assert continuation.evidence_status is TableStructureEvidenceStatus.PROPOSED
    assert result.warnings == ()


def test__table_structure__identity_is_stable_and_configuration_bound() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "tables.pdf"
    detection = _detect(fixture.read_bytes(), "identity")

    first = DeterministicTableStructureReconstructor().reconstruct(detection)
    second = DeterministicTableStructureReconstructor().reconstruct(detection)
    changed = DeterministicTableStructureReconstructor(
        TableStructureConfiguration(proposed_confidence_threshold=0.96)
    ).reconstruct(detection)

    assert first == second
    assert first.result_id == second.result_id
    assert first.result_id != changed.result_id
    assert first.structure_input.input_id != changed.structure_input.input_id
    assert changed.structures[0].evidence_status is (
        TableStructureEvidenceStatus.AMBIGUOUS
    )
    assert tuple(warning.code for warning in changed.warnings) == (
        "table_structure.low_confidence",
    )


def test__table_structure__enforces_resource_bound_before_reconstruction() -> (
    None
):
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "tables.pdf"
    detection = _detect(fixture.read_bytes(), "limit")
    reconstructor = DeterministicTableStructureReconstructor(
        TableStructureConfiguration(max_cells=3)
    )

    with pytest.raises(TableStructureLimitError, match="cells exceed"):
        reconstructor.reconstruct(detection)


def test__table_structure__contracts_are_immutable_and_reject_stale_ids() -> (
    None
):
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "tables.pdf"
    result = DeterministicTableStructureReconstructor().reconstruct(
        _detect(fixture.read_bytes(), "immutable")
    )
    structure = result.structures[0]

    with pytest.raises(FrozenInstanceError):
        structure.confidence = 0.0  # type: ignore[misc]
    with pytest.raises(ValueError, match="structure-input ID is inconsistent"):
        replace(result.structure_input, input_id="stale-input")
    with pytest.raises(ValueError, match="structure ID is inconsistent"):
        replace(structure, confidence=0.0)
    with pytest.raises(ValueError, match="cell ID is inconsistent"):
        replace(structure.cells[0], proposed_text="corrected text")
    with pytest.raises(ValueError, match="result ID is inconsistent"):
        replace(result, result_id="table-structure-result:sha256:" + "0" * 64)
