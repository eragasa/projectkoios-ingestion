from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from typing import Any

import pytest
from projectkoios.ingestion import (
    CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION,
    CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION,
    ClassificationDisposition,
    CleanTranscriptV2Configuration,
    CleanTranscriptV2ExclusionReason,
    CleanTranscriptV2Status,
    DehyphenationOutcome,
    DerivationAuditInput,
    DerivationAuditStatus,
    DerivationAuditValidator,
    DeterministicArticleStructureAnalyzer,
    DeterministicCleanTranscriptV2Projector,
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicLayoutProcessor,
    DeterministicStructuredTranscriptionComposer,
    DeterministicTableCandidateDetector,
    DeterministicTableStructureReconstructor,
    PageNumberMethod,
    PageNumberOutcome,
    PublisherFrontMatterKind,
    PyMuPdfExtractor,
    SourceDocument,
    TranscriptionInput,
)

pymupdf: Any = pytest.importorskip("pymupdf")


def _pdf() -> bytes:
    document = pymupdf.open()
    bodies = (
        (
            "electronic-\nstructure remains ambiguous",
            "Copyright 2026 Example Publisher",
            "private X glyph",
            "100",
        ),
        (
            "A tight-binding reference appears here.",
            "The tight-\nbinding model is retained.",
        ),
        (
            "An international reference appears here.",
            "The inter-\nnational result is joined.",
        ),
    )
    for page_index, lines in enumerate(bodies):
        page = document.new_page(width=420, height=420)
        page.insert_text((30, 25), "Repeated Journal Header", fontsize=9)
        for line_index, text in enumerate(lines):
            y0 = 90 + line_index * 55
            page.insert_textbox(
                (30, y0, 380, y0 + 45),
                text,
                fontsize=11,
            )
        page.insert_text((205, 400), str(page_index + 1), fontsize=9)
    payload = document.tobytes()
    document.close()
    return payload


def _pipeline(*, replacement_split: str | None = None):
    payload = _pdf()
    source = SourceDocument.from_bytes(
        payload,
        source_id="fixture:clean-transcript-v2",
        media_type="application/pdf",
        locator="memory://clean-transcript-v2.pdf",
    )
    extraction = PyMuPdfExtractor().extract(source, BytesIO(payload))
    document = extraction.document
    pages = []
    private_block_id = None
    for page in document.pages:
        blocks = []
        for block in page.blocks:
            if (
                replacement_split is not None
                and block.text is not None
                and "electronic-\nstructure" in block.text
            ):
                block = replace(block, text=replacement_split)
            if block.text is not None and "private X glyph" in block.text:
                private_block_id = block.block_id
                block = replace(block, text=block.text.replace("X", "\ue000"))
            blocks.append(block)
        pages.append(replace(page, blocks=tuple(blocks)))
    assert private_block_id is not None
    document = replace(document, pages=tuple(pages))
    extraction = replace(extraction, document=document)
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
    return payload, extraction, layouts, transcription, private_block_id


def test__clean_transcript_v2__is_additive_deterministic_contract() -> None:
    _, _, layouts, transcription, _ = _pipeline()
    projector = DeterministicCleanTranscriptV2Projector()

    first = projector.project(transcription, layouts)
    second = projector.project(transcription, layouts)

    assert first == second
    assert first.contract_version == CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION
    assert first.artifact_generation == CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION
    assert first.status is CleanTranscriptV2Status.AUTOMATED_UNREVIEWED
    assert first.artifact_id != first.transcription_result_id
    with pytest.raises(ValueError, match="artifact ID"):
        replace(first, artifact_id="tampered")


def test__clean_transcript_v2__uses_positive_dehyphenation_evidence() -> None:
    _, _, layouts, transcription, _ = _pipeline()

    result = DeterministicCleanTranscriptV2Projector().project(
        transcription, layouts
    )

    outcomes = {
        item.candidate_joined.casefold(): item.outcome
        for item in result.dehyphenation_decisions
    }
    assert outcomes["electronicstructure"] is (
        DehyphenationOutcome.PRESERVE_BREAK_CONSERVATIVELY
    )
    assert outcomes["tightbinding"] is DehyphenationOutcome.PRESERVE_HYPHEN
    assert outcomes["international"] is DehyphenationOutcome.JOIN
    assert "electronicstructure" not in result.text.casefold()
    assert "electronic- structure" in result.text.casefold()
    assert "tight-binding model" in result.text.casefold()
    assert "international result" in result.text.casefold()
    assert all(item.raw_fragment for item in result.dehyphenation_decisions)
    assert all(item.source_spans for item in result.dehyphenation_decisions)


@pytest.mark.parametrize(
    ("source_split", "wrong_join"),
    (
        ("electronic-\nstructure", "electronicstructure"),
        ("tight-\nbinding", "tightbinding"),
        ("high-\nthroughput", "highthroughput"),
        ("first-\nprinciples", "firstprinciples"),
        ("electron-\nphonon", "electronphonon"),
        ("state-\nof", "stateof"),
    ),
)
def test__clean_transcript_v2__known_bad_compounds_never_join_without_evidence(
    source_split: str, wrong_join: str
) -> None:
    _, _, layouts, transcription, _ = _pipeline(replacement_split=source_split)

    result = DeterministicCleanTranscriptV2Projector().project(
        transcription, layouts
    )

    assert wrong_join not in result.text.casefold()
    decision = next(
        item
        for item in result.dehyphenation_decisions
        if item.candidate_joined.casefold() == wrong_join
    )
    assert decision.outcome is not DehyphenationOutcome.JOIN


def test__clean_transcript_v2__does_not_exclude_plot_axis_number() -> None:
    _, _, layouts, transcription, _ = _pipeline()

    result = DeterministicCleanTranscriptV2Projector().project(
        transcription, layouts
    )

    plot = next(
        item
        for item in result.page_number_classifications
        if item.raw_text.strip() == "100"
    )
    assert plot.outcome is PageNumberOutcome.NOT_PAGE_NUMBER
    assert plot.method is PageNumberMethod.OUTSIDE_MARGIN
    assert "100" in result.text
    page_numbers = {
        item.raw_text.strip()
        for item in result.page_number_classifications
        if item.outcome is PageNumberOutcome.PAGE_NUMBER
    }
    assert page_numbers == {"1", "2", "3"}
    assert {
        item.raw_text.strip()
        for item in result.exclusions
        if item.reason is CleanTranscriptV2ExclusionReason.PAGE_NUMBER
    } == page_numbers


def test__clean_transcript_v2__retains_private_use_glyph_with_locator() -> None:
    _, _, layouts, transcription, private_block_id = _pipeline()

    result = DeterministicCleanTranscriptV2Projector().project(
        transcription, layouts
    )

    assert len(result.private_use_glyph_findings) == 1
    finding = result.private_use_glyph_findings[0]
    assert finding.block_id == private_block_id
    assert finding.code_point == "U+E000"
    assert finding.raw_character == "\ue000"
    assert finding.source_spans
    block = next(
        item for item in result.blocks if item.block_id == private_block_id
    )
    assert block.raw_text[finding.character_offset] == "\ue000"
    assert "\ue000" in block.clean_text
    assert "private_use_glyph_retained" in result.warnings


def test__clean_transcript_v2__types_publisher_material_without_deleting() -> (
    None
):
    _, _, layouts, transcription, _ = _pipeline()

    included = DeterministicCleanTranscriptV2Projector().project(
        transcription, layouts
    )

    classification = next(
        item
        for item in included.publisher_front_matter
        if item.kind is PublisherFrontMatterKind.LICENSING
    )
    assert classification.disposition is ClassificationDisposition.INCLUDED
    assert "Copyright 2026 Example Publisher" in included.text

    excluded = DeterministicCleanTranscriptV2Projector(
        CleanTranscriptV2Configuration(
            excluded_publisher_front_matter=(
                PublisherFrontMatterKind.LICENSING,
            )
        )
    ).project(transcription, layouts)
    assert "Copyright 2026 Example Publisher" not in excluded.text
    excluded_classification = next(
        item
        for item in excluded.publisher_front_matter
        if item.kind is PublisherFrontMatterKind.LICENSING
    )
    assert excluded_classification.disposition is (
        ClassificationDisposition.EXCLUDED
    )
    assert any(
        item.reason is CleanTranscriptV2ExclusionReason.PUBLISHER_FRONT_MATTER
        and item.decision_id == excluded_classification.classification_id
        for item in excluded.exclusions
    )


def test__clean_transcript_v2__passes_transitive_derivation_audit() -> None:
    payload, extraction, layouts, transcription, _ = _pipeline()
    artifact = DeterministicCleanTranscriptV2Projector().project(
        transcription, layouts
    )
    transcription_input = transcription.transcription_input
    table_structure = transcription_input.table_structure_result
    table_detection = table_structure.structure_input.detection_result

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=payload,
            extraction_result=extraction,
            layout_results=layouts,
            structure_analyses=(transcription_input.structure_analysis,),
            equation_results=(transcription_input.equation_detection_result,),
            table_detection_results=(table_detection,),
            table_structure_results=(table_structure,),
            figure_results=(transcription_input.figure_detection_result,),
            transcription_results=(transcription,),
            clean_transcript_v2_artifacts=(artifact,),
        )
    )

    assert report.status is DerivationAuditStatus.PASSED
    assert not report.findings
    assert (
        dict(report.audited_layer_counts)["clean_transcript_v2_artifacts"]
        == "1"
    )
