from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pytest
from projectkoios.ingestion import (
    DeterministicArticleStructureAnalyzer,
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    DeterministicStructuredTranscriptionComposer,
    DeterministicTableCandidateDetector,
    DeterministicTableStructureReconstructor,
    PyMuPdfExtractor,
    SourceDocument,
    TranscriptionInput,
)
from projectkoios.ingestion.transcript_projection import (
    CleanTranscriptExclusionReason,
    CleanTranscriptStatus,
    DeterministicCleanTranscriptProjector,
)

pymupdf: Any = pytest.importorskip("pymupdf")


def _pdf() -> bytes:
    document = pymupdf.open()
    for page_index in range(3):
        page = document.new_page(width=420, height=420)
        page.insert_text(
            (30, 25),
            f"Journal 2026 page {page_index + 1}",
            fontsize=9,
        )
        page.insert_text(
            (30, 100),
            f"Body evidence for physical page {page_index + 1}.",
            fontsize=11,
        )
        if page_index == 0:
            page.insert_textbox(
                (30, 130, 220, 180),
                "inter-\nnational evidence",
                fontsize=11,
            )
        page.insert_text((205, 400), str(page_index + 1), fontsize=9)
    payload = document.tobytes()
    document.close()
    return payload


def _pipeline(payload: bytes):
    source = SourceDocument.from_bytes(
        payload,
        source_id="fixture:clean-transcript",
        media_type="application/pdf",
        locator="memory://clean-transcript.pdf",
    )
    document = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    layouts = DeterministicLayoutProcessor().analyze(document)
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    equations = DeterministicEquationCandidateDetector().detect_with_layout(
        document, BytesIO(payload), layouts
    )
    table_detection = DeterministicTableCandidateDetector().detect_with_layout(
        document, BytesIO(payload), layouts
    )
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector().detect_with_layout(
        document, BytesIO(payload), layouts
    )
    transcription = DeterministicStructuredTranscriptionComposer().compose(
        TranscriptionInput.create(
            document=document,
            structure_analysis=structure,
            equation_detection_result=equations,
            table_structure_result=tables,
            figure_detection_result=figures,
        )
    )
    return layouts, transcription


def test__clean_transcript__is_deterministic_and_source_linked() -> None:
    layouts, transcription = _pipeline(_pdf())
    projector = DeterministicCleanTranscriptProjector()

    first = projector.project(transcription, layouts)
    second = projector.project(transcription, layouts)

    assert first == second
    assert first.status is CleanTranscriptStatus.AUTOMATED_UNREVIEWED
    assert first.transcription_result_id == transcription.result_id
    assert len(first.pages) == 3
    assert first.text.count("[[PAGE physical=") == 3
    assert "Body evidence for physical page 1." in first.text
    assert "international evidence" in first.text
    assert "Journal 2026 page" not in first.text
    assert (
        first.text_sha256
        == hashlib.sha256(first.text.encode("utf-8")).hexdigest()
    )
    assert all(block.raw_text for block in first.blocks)
    assert all(block.source_spans for block in first.blocks)


def test__clean_transcript__retains_excluded_margin_evidence() -> None:
    layouts, transcription = _pipeline(_pdf())

    result = DeterministicCleanTranscriptProjector().project(
        transcription, layouts
    )

    reasons = {item.reason for item in result.exclusions}
    assert CleanTranscriptExclusionReason.REPEATED_MARGIN in reasons
    assert CleanTranscriptExclusionReason.PAGE_NUMBER in reasons
    assert any("Journal 2026" in item.raw_text for item in result.exclusions)
    assert all(item.source_spans for item in result.exclusions)
