from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    DeterministicEquationCandidateDetector,
    DeterministicLayoutProcessor,
    EquationCandidateKind,
    EquationDetectionConfiguration,
    EquationDetectionLimitError,
    EquationEvidenceStatus,
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    PyMuPdfExtractor,
    SourceDocument,
    SourceSpan,
)

pymupdf = pytest.importorskip("pymupdf")


def _source(payload: bytes, *, suffix: str = "default") -> SourceDocument:
    return SourceDocument.from_bytes(
        payload,
        source_id=f"article:equation:{suffix}",
        media_type="application/pdf",
        locator=f"memory://equation-{suffix}.pdf",
    )


def _pdf(
    lines: tuple[str, ...],
    *,
    rotation: int = 0,
) -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=420, height=300)
    for index, text in enumerate(lines):
        page.insert_text((50, 55 + index * 70), text, fontsize=12)
    if rotation:
        page.set_rotation(rotation)
    payload = document.tobytes()
    document.close()
    return payload


def _extract(payload: bytes, *, suffix: str = "default"):
    source = _source(payload, suffix=suffix)
    document = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    return source, document


def _detect(
    payload: bytes,
    *,
    suffix: str = "default",
    configuration: EquationDetectionConfiguration | None = None,
):
    _, document = _extract(payload, suffix=suffix)
    detector = DeterministicEquationCandidateDetector(configuration)
    return detector.detect(document, BytesIO(payload))


def test__equation_detector__detects_fixture_display_and_label() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pdf" / "equations.pdf"
    payload = fixture.read_bytes()

    result = _detect(payload, suffix="fixture")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.kind is EquationCandidateKind.DISPLAY
    assert candidate.raw_text == "E = m c^2    (1)"
    assert candidate.source_label == "(1)"
    assert candidate.evidence_status is EquationEvidenceStatus.PROPOSED
    assert candidate.preceding_context is not None
    assert candidate.following_context is not None
    assert candidate.rendered_region.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert candidate.rendered_region.selection_was_full_page is False
    assert candidate.source_block_id in {
        block.block_id
        for page in result.detection_input.document.pages
        for block in page.blocks
    }


def test__equation_detector__detects_inline_offsets_and_ambiguity() -> None:
    text = "The relation $E = m c^2$ follows from the assumptions."
    payload = _pdf(("Before context.", text, "After context."))

    result = _detect(payload, suffix="inline")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.kind is EquationCandidateKind.INLINE
    assert candidate.raw_text == "E = m c^2"
    span = candidate.source_spans[0]
    assert span.start_offset is not None
    assert span.end_offset is not None
    block = next(
        block
        for page in result.detection_input.document.pages
        for block in page.blocks
        if block.block_id == candidate.source_block_id
    )
    assert block.text is not None
    assert block.text[span.start_offset : span.end_offset] == candidate.raw_text
    assert candidate.preceding_context is not None
    assert candidate.following_context is not None
    assert candidate.evidence_status is EquationEvidenceStatus.PROPOSED


def test__equation_detector__keeps_delimited_block_as_inline() -> None:
    payload = _pdf((r"\(x + y = z\)",))

    result = _detect(payload, suffix="delimited-block")

    candidate = result.candidates[0]
    assert candidate.kind is EquationCandidateKind.INLINE
    assert candidate.raw_text == "x + y = z"


def test__equation_detector__marks_weak_relational_inline_ambiguous() -> None:
    text = "For this case x = y follows."
    payload = _pdf((text,))

    result = _detect(payload, suffix="ambiguous")

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.kind is EquationCandidateKind.INLINE
    assert candidate.evidence_status is EquationEvidenceStatus.AMBIGUOUS
    assert candidate.warning_ids
    assert any(
        warning.code == "equation.ambiguous_candidate"
        and candidate.candidate_id in warning.object_ids
        for warning in result.warnings
    )


def test__equation_detector__requires_exact_pdf_bytes_for_rendering() -> None:
    payload = _pdf(("x = y    (1)",))
    _, document = _extract(payload, suffix="exact-bytes")

    with pytest.raises(ValueError, match="source bytes"):
        DeterministicEquationCandidateDetector().detect(
            document, BytesIO(b"not the source PDF")
        )


def test__equation_detector__does_not_promote_equation_prose() -> None:
    payload = _pdf(
        (
            "Equation page: raw native characters only",
            "No equation interpretation is asserted.",
        )
    )

    result = _detect(payload, suffix="prose")

    assert not result.candidates
    assert not result.warnings


def test__equation_detector__warns_when_geometry_cannot_be_rendered() -> None:
    payload = _pdf(("E = m c^2    (1)",))
    source = _source(payload, suffix="missing-geometry")
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                source_object_id="equation:no-geometry",
            ),
        ),
        extraction_method="synthetic",
        confidence=1.0,
        text="E = m c^2    (1)",
    )
    document = ExtractedDocument.create(
        source=source,
        pages=(
            ExtractedPage(
                page_index=0,
                width=420.0,
                height=300.0,
                blocks=(block,),
                coordinate_system=("pymupdf_unrotated_cropbox_points_top_left"),
            ),
        ),
    )

    result = DeterministicEquationCandidateDetector().detect(
        document, BytesIO(payload)
    )

    assert not result.candidates
    assert result.warnings[0].code == "equation.missing_geometry"
    assert result.warnings[0].object_ids == (block.block_id,)


def test__equation_detector__supports_rotated_page_rendering() -> None:
    payload = _pdf(("E = m c^2    (2)",), rotation=90)

    result = _detect(payload, suffix="rotated")

    candidate = result.candidates[0]
    assert candidate.source_label == "(2)"
    assert candidate.rendered_region.page_rotation_degrees == 90
    assert candidate.rendered_region.page_index == 0


def test__equation_detector__rejects_stale_layout_evidence() -> None:
    payload = _pdf(("E = m c^2    (1)",))
    _, document = _extract(payload, suffix="current")
    other_payload = _pdf(("x + y = z    (3)",))
    _, other = _extract(other_payload, suffix="other")
    stale = DeterministicLayoutProcessor().analyze(other)

    with pytest.raises(ValueError, match="does not match"):
        DeterministicEquationCandidateDetector().detect_with_layout(
            document,
            BytesIO(payload),
            stale,
        )


def test__equation_detector__enforces_candidate_limit_before_rendering() -> (
    None
):
    payload = _pdf(("x = y    (1)", "a = b    (2)"))

    with pytest.raises(EquationDetectionLimitError, match="max_candidates"):
        _detect(
            payload,
            suffix="limit",
            configuration=EquationDetectionConfiguration(max_candidates=1),
        )


def test__equation_detector__enforces_rendered_aggregate_limit() -> None:
    payload = _pdf(("x = y    (1)",))

    with pytest.raises(
        EquationDetectionLimitError, match="max_total_rendered_pixels"
    ):
        _detect(
            payload,
            suffix="render-limit",
            configuration=EquationDetectionConfiguration(
                max_total_rendered_pixels=1
            ),
        )


def test__equation_detector__is_deterministic_and_immutable() -> None:
    payload = _pdf(("Before.", "x + y = z    (4)", "After."))

    first = _detect(payload, suffix="stable")
    second = _detect(payload, suffix="stable")

    assert first == second
    assert first.result_id == second.result_id
    assert first.candidates[0].candidate_id == second.candidates[0].candidate_id
    with pytest.raises(FrozenInstanceError):
        first.result_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="inconsistent"):
        replace(first, result_id="changed")
    with pytest.raises(ValueError, match="inconsistent"):
        replace(first.candidates[0], candidate_id="changed")
