from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from functools import cache
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    DeterministicArticleStructureAnalyzer,
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicTableCandidateDetector,
    DeterministicTableStructureReconstructor,
    EquationDetectionResult,
    ExtractedBlock,
    ExtractedDocument,
    FigureDetectionResult,
    PyMuPdfExtractor,
    SourceDocument,
    StructureAnalysis,
    TableStructureResult,
)
from projectkoios.ingestion import (
    DeterministicStructuredTranscriptionComposer as PublicComposer,
)
from projectkoios.ingestion.protocols import StructuredTranscriptionComposer
from projectkoios.ingestion.transcription import (
    DeterministicStructuredTranscriptionComposer,
    StructuredTranscriptionResult,
    TranscriptionConfiguration,
    TranscriptionEvidenceStatus,
    TranscriptionInput,
    TranscriptionItemKind,
    TranscriptionLimitError,
    TranscriptionOmission,
    TranscriptionOmissionReason,
    TranscriptionOrderStatus,
    TranscriptionSourceObjectKind,
    TranscriptionStatus,
    build_transcription_cache_key,
)

pytest.importorskip("pymupdf")


@cache
def _pipeline(fixture_name: str):
    fixture = Path(__file__).parent / "fixtures" / "pdf" / f"{fixture_name}.pdf"
    payload = fixture.read_bytes()
    source = SourceDocument.from_bytes(
        payload,
        source_id=f"article:structured-transcription:{fixture_name}",
        media_type="application/pdf",
        locator=f"memory://{fixture_name}.pdf",
    )
    document = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    equations = DeterministicEquationCandidateDetector().detect(
        document, BytesIO(payload)
    )
    table_detection = DeterministicTableCandidateDetector().detect(
        document, BytesIO(payload)
    )
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector().detect(
        document, BytesIO(payload)
    )
    transcription_input = TranscriptionInput.create(
        document=document,
        structure_analysis=structure,
        equation_detection_result=equations,
        table_structure_result=tables,
        figure_detection_result=figures,
    )
    result = DeterministicStructuredTranscriptionComposer().compose(
        transcription_input
    )
    return payload, transcription_input, result


def _uncertain_input() -> TranscriptionInput:
    payload, base, _result = _pipeline("born-digital-text")
    document = base.document
    pages = []
    for page in document.pages:
        blocks = []
        for block in page.blocks:
            spans = tuple(
                replace(span, bounding_box=None) for span in block.source_spans
            )
            blocks.append(
                ExtractedBlock.create(
                    kind=block.kind,
                    source_spans=spans,
                    extraction_method=block.extraction_method,
                    confidence=block.confidence,
                    text=block.text,
                    asset_id=block.asset_id,
                    warning_ids=block.warning_ids,
                    asset_media_type=block.asset_media_type,
                    asset_mask_id=block.asset_mask_id,
                    asset_mask_media_type=block.asset_mask_media_type,
                )
            )
        pages.append(replace(page, blocks=tuple(blocks)))
    altered = ExtractedDocument.create(
        source=document.source,
        pages=tuple(pages),
        metadata=document.metadata,
        table_of_contents=document.table_of_contents,
        warning_ids=document.warning_ids,
    )
    structure = StructureAnalysis.create(
        source=altered.source,
        nodes=(),
        warnings=(),
        layout_result_ids=(),
        input_block_ids=tuple(
            block.block_id for page in altered.pages for block in page.blocks
        ),
        processor_name="empty-fixture-structure",
        processor_version="1",
        configuration_digest="empty-fixture-structure-v1",
    )
    equations = DeterministicEquationCandidateDetector().detect(
        altered, BytesIO(payload)
    )
    table_detection = DeterministicTableCandidateDetector().detect(
        altered, BytesIO(payload)
    )
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector().detect(
        altered, BytesIO(payload)
    )
    return TranscriptionInput.create(
        document=altered,
        structure_analysis=structure,
        equation_detection_result=equations,
        table_structure_result=tables,
        figure_detection_result=figures,
    )


def test__structured_transcription__normalizes_exact_source_text() -> None:
    _payload, transcription_input, result = _pipeline("born-digital-text")
    page_anchors = tuple(
        item
        for item in result.items
        if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR
    )
    text_items = tuple(item for item in result.items if item.source_texts)

    assert len(page_anchors) == len(transcription_input.document.pages)
    assert tuple(item.order_index for item in result.items) == tuple(
        range(len(result.items))
    )
    assert text_items
    for item in text_items:
        expected = " ".join("\n".join(item.source_texts).split())
        assert item.normalized_text == expected
        assert item.normalization_method == "collapse_unicode_whitespace_v1"
        assert item.source_block_ids
        assert item.source_spans
    assert not hasattr(result, "citekey")
    assert not hasattr(result, "vault_path")
    assert not hasattr(result, "reading_status")
    assert not hasattr(result, "scientific_acceptance")


def test__structured_transcription__retains_equation_candidate() -> None:
    _payload, transcription_input, result = _pipeline("equations")
    candidate = transcription_input.equation_detection_result.candidates[0]
    equation = next(
        item
        for item in result.items
        if item.source_object_kind
        is TranscriptionSourceObjectKind.EQUATION_CANDIDATE
    )

    assert equation.item_kind is TranscriptionItemKind.EQUATION
    assert equation.source_object_id == candidate.candidate_id
    assert equation.source_block_ids == (candidate.source_block_id,)
    assert equation.source_spans == candidate.source_spans
    assert equation.source_texts == (candidate.raw_text,)
    assert equation.normalized_text == " ".join(candidate.raw_text.split())
    assert equation.evidence_status in (
        TranscriptionEvidenceStatus.PROPOSED,
        TranscriptionEvidenceStatus.AMBIGUOUS,
    )


def test__structured_transcription__retains_table_structure() -> None:
    _payload, transcription_input, result = _pipeline("tables")
    structure = transcription_input.table_structure_result.structures[0]
    table = next(
        item
        for item in result.items
        if item.source_object_kind
        is TranscriptionSourceObjectKind.TABLE_STRUCTURE
    )

    assert table.item_kind is TranscriptionItemKind.TABLE
    assert table.source_object_id == structure.structure_id
    assert table.normalized_text is None
    assert structure.cells
    assert any(
        omission.reason
        is TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT
        and table.item_id in omission.represented_by_item_ids
        for omission in result.omissions
    )


def test__structured_transcription__retains_figure_candidate() -> None:
    _payload, transcription_input, result = _pipeline("figures")
    candidate = transcription_input.figure_detection_result.candidates[0]
    figure = next(
        item
        for item in result.items
        if item.source_object_kind
        is TranscriptionSourceObjectKind.FIGURE_CANDIDATE
    )

    assert figure.item_kind is TranscriptionItemKind.FIGURE
    assert figure.source_object_id == candidate.candidate_id
    assert figure.source_spans == candidate.source_spans
    assert figure.normalized_text is None
    assert candidate.components


def test__structured_transcription__makes_uncertain_order_explicit() -> None:
    transcription_input = _uncertain_input()
    result = DeterministicStructuredTranscriptionComposer().compose(
        transcription_input
    )
    fallback = next(
        item
        for item in result.items
        if item.source_object_kind is TranscriptionSourceObjectKind.RAW_BLOCK
    )

    assert fallback.order_status is (
        TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER
    )
    assert fallback.warning_ids
    assert {warning.code for warning in result.warnings} == {
        "transcription.raw_block_fallback",
        "transcription.order_uncertain",
    }
    assert result.status is TranscriptionStatus.PROPOSED_WITH_UNCERTAINTY


def test__structured_transcription__cache_identity_covers_all_inputs() -> None:
    _payload, first_input, _result = _pipeline("born-digital-text")
    structure = first_input.structure_analysis
    changed_structure = StructureAnalysis.create(
        source=first_input.document.source,
        nodes=structure.nodes,
        warnings=structure.warnings,
        layout_result_ids=structure.layout_result_ids,
        input_block_ids=structure.input_block_ids,
        processor_name=structure.processor_name or "structure",
        processor_version="changed",
        configuration_digest=structure.configuration_digest or "structure",
    )
    equations = first_input.equation_detection_result
    changed_equations = EquationDetectionResult.create(
        detection_input=equations.detection_input,
        candidates=equations.candidates,
        warnings=equations.warnings,
        processor_name=equations.processor_name,
        processor_version="changed",
    )
    tables = first_input.table_structure_result
    changed_tables = TableStructureResult.create(
        structure_input=tables.structure_input,
        structures=tables.structures,
        warnings=tables.warnings,
        processor_name=tables.processor_name,
        processor_version="changed",
    )
    figures = first_input.figure_detection_result
    changed_figures = FigureDetectionResult.create(
        detection_input=figures.detection_input,
        candidates=figures.candidates,
        warnings=figures.warnings,
        processor_name=figures.processor_name,
        processor_version="changed",
    )

    def replace_input(
        *,
        structure_analysis: StructureAnalysis = first_input.structure_analysis,
        equation_detection_result: EquationDetectionResult = (
            first_input.equation_detection_result
        ),
        table_structure_result: TableStructureResult = (
            first_input.table_structure_result
        ),
        figure_detection_result: FigureDetectionResult = (
            first_input.figure_detection_result
        ),
        configuration: TranscriptionConfiguration = first_input.configuration,
    ) -> TranscriptionInput:
        return TranscriptionInput.create(
            document=first_input.document,
            structure_analysis=structure_analysis,
            equation_detection_result=equation_detection_result,
            table_structure_result=table_structure_result,
            figure_detection_result=figure_detection_result,
            configuration=configuration,
        )

    changed_configuration = replace_input(
        configuration=TranscriptionConfiguration(max_items=100)
    )
    changed_inputs = (
        replace_input(structure_analysis=changed_structure),
        replace_input(equation_detection_result=changed_equations),
        replace_input(table_structure_result=changed_tables),
        replace_input(figure_detection_result=changed_figures),
    )
    baseline = build_transcription_cache_key(first_input)

    assert first_input.document_evidence_id.startswith(
        "structured-transcription-document-evidence:sha256:"
    )
    keys = {
        baseline,
        *(build_transcription_cache_key(value) for value in changed_inputs),
        build_transcription_cache_key(changed_configuration),
        build_transcription_cache_key(first_input, processor_version="2"),
    }
    assert len(keys) == 7


def test__structured_transcription__rejects_cross_source_inputs() -> None:
    _payload, equations_input, _result = _pipeline("equations")
    _other_payload, tables_input, _other_result = _pipeline("tables")

    with pytest.raises(ValueError, match="table result must retain"):
        TranscriptionInput.create(
            document=equations_input.document,
            structure_analysis=equations_input.structure_analysis,
            equation_detection_result=equations_input.equation_detection_result,
            table_structure_result=tables_input.table_structure_result,
            figure_detection_result=equations_input.figure_detection_result,
        )


def test__structured_transcription__enforces_artifact_and_output_limits() -> (
    None
):
    _payload, equations_input, _result = _pipeline("equations")
    with pytest.raises(TranscriptionLimitError, match="input artifacts"):
        TranscriptionInput.create(
            document=equations_input.document,
            structure_analysis=equations_input.structure_analysis,
            equation_detection_result=equations_input.equation_detection_result,
            table_structure_result=equations_input.table_structure_result,
            figure_detection_result=equations_input.figure_detection_result,
            configuration=TranscriptionConfiguration(
                max_input_artifact_bytes=1
            ),
        )

    _payload, born_input, _result = _pipeline("born-digital-text")
    limited = TranscriptionInput.create(
        document=born_input.document,
        structure_analysis=born_input.structure_analysis,
        equation_detection_result=born_input.equation_detection_result,
        table_structure_result=born_input.table_structure_result,
        figure_detection_result=born_input.figure_detection_result,
        configuration=TranscriptionConfiguration(max_items=1),
    )
    with pytest.raises(TranscriptionLimitError, match="items exceed"):
        DeterministicStructuredTranscriptionComposer().compose(limited)


def test__structured_transcription__rejects_false_provenance() -> None:
    _payload, transcription_input, result = _pipeline("tables")
    geometric = next(
        item
        for item in result.items
        if item.order_status is TranscriptionOrderStatus.PROPOSED_GEOMETRIC
    )
    altered_items = tuple(
        replace(item, order_status=TranscriptionOrderStatus.PROPOSED_STRUCTURE)
        if item.item_id == geometric.item_id
        else item
        for item in result.items
    )
    with pytest.raises(ValueError, match="order evidence is inconsistent"):
        StructuredTranscriptionResult.create(
            transcription_input=transcription_input,
            items=altered_items,
            omissions=result.omissions,
            warnings=result.warnings,
            processor_name=result.processor_name,
            processor_version=result.processor_version,
        )

    omission = next(
        item
        for item in result.omissions
        if item.reason
        is TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT
    )
    altered_omission = TranscriptionOmission.create(
        omitted_object_id=omission.omitted_object_id,
        source_block_id=omission.source_block_id,
        source_spans=omission.source_spans,
        reason=TranscriptionOmissionReason.REPRESENTED_BY_EARLIER_ITEM,
        represented_by_item_ids=omission.represented_by_item_ids,
        warning_ids=omission.warning_ids,
        evidence=omission.evidence,
    )
    with pytest.raises(ValueError, match="has a typed replacement"):
        StructuredTranscriptionResult.create(
            transcription_input=transcription_input,
            items=result.items,
            omissions=(altered_omission,),
            warnings=result.warnings,
            processor_name=result.processor_name,
            processor_version=result.processor_version,
        )


def test__structured_transcription__protocol_is_engine_neutral() -> None:
    assert PublicComposer is DeterministicStructuredTranscriptionComposer
    composer: StructuredTranscriptionComposer = (
        DeterministicStructuredTranscriptionComposer()
    )
    _payload, transcription_input, expected = _pipeline("born-digital-text")

    assert composer.compose(transcription_input) == expected


def test__structured_transcription__is_deterministic_and_immutable() -> None:
    _payload, transcription_input, result = _pipeline("tables")
    repeated = DeterministicStructuredTranscriptionComposer().compose(
        transcription_input
    )

    assert repeated == result
    with pytest.raises(FrozenInstanceError):
        result.items[0].order_index = 9  # type: ignore[misc]
    with pytest.raises(ValueError, match="item ID is inconsistent"):
        replace(result.items[-1], item_id="stale-item")
    with pytest.raises(ValueError, match="document evidence ID"):
        replace(
            transcription_input,
            document_evidence_id="stale-document-evidence",
        )
    with pytest.raises(ValueError, match="input ID is inconsistent"):
        replace(transcription_input, input_id="stale-input")
    with pytest.raises(ValueError, match="result ID is inconsistent"):
        replace(
            result,
            result_id="structured-transcription-result:sha256:" + "0" * 64,
        )
