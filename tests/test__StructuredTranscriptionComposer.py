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
    EquationDetectionResult,
    ExtractedBlock,
    ExtractedDocument,
    FigureDetectionResult,
    PyMuPdfExtractor,
    SourceDocument,
    StructureAnalysis,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.rendering import (
    PyMuPdfRegionRenderer,
)
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.verifier import SHA256Verifier
from projectkoios.ingestion.tables.structure.reconstructor import (
    DeterministicTableStructureReconstructor,
)
from projectkoios.ingestion.tables.structure.result import TableStructureResult
from projectkoios.ingestion.transcription.artifact_inventory import (
    TranscriptionInputArtifactInventory,
)
from projectkoios.ingestion.transcription.cache_identity import (
    TranscriptionCacheIdentity,
)
from projectkoios.ingestion.transcription.composer import (
    DeterministicStructuredTranscriptionComposer,
)
from projectkoios.ingestion.transcription.configuration import (
    TranscriptionConfiguration,
)
from projectkoios.ingestion.transcription.evidence_status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item_kind import (
    TranscriptionItemKind,
)
from projectkoios.ingestion.transcription.limit_error import (
    TranscriptionLimitError,
)
from projectkoios.ingestion.transcription.omission import (
    TranscriptionOmission,
)
from projectkoios.ingestion.transcription.omission_reason import (
    TranscriptionOmissionReason,
)
from projectkoios.ingestion.transcription.order_status import (
    TranscriptionOrderStatus,
)
from projectkoios.ingestion.transcription.result_status import (
    TranscriptionStatus,
)
from projectkoios.ingestion.transcription.source_object_kind import (
    TranscriptionSourceObjectKind,
)
from projectkoios.ingestion.transcription.structured_request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.structured_result import (
    StructuredTranscriptionResult,
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
    equations = DeterministicEquationCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer()
    ).detect(document, BytesIO(payload))
    table_detection = DeterministicTableCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer(
            max_total_pixels=100_000_000,
            max_total_raster_bytes=100_000_000,
        )
    ).detect(document, BytesIO(payload))
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer(
            max_total_pixels=100_000_000,
            max_total_raster_bytes=100_000_000,
        )
    ).detect(document, BytesIO(payload))
    transcription_input = StructuredTranscriptionRequest.create(
        document=document,
        structure_analysis=structure,
        equation_detection_result=equations,
        table_structure_result=tables,
        figure_detection_result=figures,
    )
    result = DeterministicStructuredTranscriptionComposer().action(
        request=transcription_input
    )
    return payload, transcription_input, result


def _uncertain_input() -> StructuredTranscriptionRequest:
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
    equations = DeterministicEquationCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer()
    ).detect(altered, BytesIO(payload))
    table_detection = DeterministicTableCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer(
            max_total_pixels=100_000_000,
            max_total_raster_bytes=100_000_000,
        )
    ).detect(altered, BytesIO(payload))
    tables = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector(
        region_renderer=PyMuPdfRegionRenderer(
            max_total_pixels=100_000_000,
            max_total_raster_bytes=100_000_000,
        )
    ).detect(altered, BytesIO(payload))
    return StructuredTranscriptionRequest.create(
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
    result = DeterministicStructuredTranscriptionComposer().action(
        request=transcription_input
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


def test__structured_transcription__derives_compact_artifact_inventory() -> (
    None
):
    expected = {
        "born-digital-text": (
            "transcription-input-artifact-inventory:sha256:6bfb9fc30fe5012cb33ec86a2317323ebb00444d472ef028275256bed801c213",
            0,
            0,
            0,
        ),
        "equations": (
            "transcription-input-artifact-inventory:sha256:1649a798027e1738178789ae7dcc03ec13bf0250a605f99abe31b8300b75724a",
            2070,
            0,
            2070,
        ),
        "tables": (
            "transcription-input-artifact-inventory:sha256:9a39733c16069714edd4f7c0a1494b67943b74578d5080c9f28f46237a895a18",
            9101,
            0,
            9101,
        ),
        "figures": (
            "transcription-input-artifact-inventory:sha256:f853e305ae591b449dee1c089befe29f68066abdf53cf834cb8daf4ceccf9221",
            0,
            100,
            100,
        ),
    }
    inventories = {}
    for fixture_name, expected_values in expected.items():
        _payload, request, _result = _pipeline(fixture_name)
        inventory = TranscriptionInputArtifactInventory.derive(
            request.equation_detection_result,
            request.table_structure_result,
            request.figure_detection_result,
        )
        inventories[fixture_name] = inventory
        assert (
            inventory.inventory_id,
            inventory.rendered_bytes,
            inventory.embedded_bytes,
            inventory.total_bytes,
        ) == expected_values
        assert inventory == TranscriptionInputArtifactInventory.derive(
            request.equation_detection_result,
            request.table_structure_result,
            request.figure_detection_result,
        )

    assert len({value.inventory_id for value in inventories.values()}) == 4


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
    ) -> StructuredTranscriptionRequest:
        return StructuredTranscriptionRequest.create(
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
    baseline = TranscriptionCacheIdentity.create(first_input).cache_key

    assert first_input.document_evidence_id.startswith(
        "structured-transcription-document-evidence:sha256:"
    )
    keys = {
        baseline,
        *(
            TranscriptionCacheIdentity.create(value).cache_key
            for value in changed_inputs
        ),
        TranscriptionCacheIdentity.create(changed_configuration).cache_key,
        TranscriptionCacheIdentity.create(
            first_input,
            processor_version="2",
        ).cache_key,
    }
    assert len(keys) == 7


def test__structured_transcription__rejects_cross_source_inputs() -> None:
    _payload, equations_input, _result = _pipeline("equations")
    _other_payload, tables_input, _other_result = _pipeline("tables")

    with pytest.raises(ValueError, match="table result must retain"):
        StructuredTranscriptionRequest.create(
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
        StructuredTranscriptionRequest.create(
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
    limited = StructuredTranscriptionRequest.create(
        document=born_input.document,
        structure_analysis=born_input.structure_analysis,
        equation_detection_result=born_input.equation_detection_result,
        table_structure_result=born_input.table_structure_result,
        figure_detection_result=born_input.figure_detection_result,
        configuration=TranscriptionConfiguration(max_items=1),
    )
    with pytest.raises(TranscriptionLimitError, match="items exceed"):
        DeterministicStructuredTranscriptionComposer().action(request=limited)


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


def test__structured_transcription__uses_action_family_base_objects() -> None:
    actionizer = DeterministicStructuredTranscriptionComposer()
    _payload, request, expected = _pipeline("born-digital-text")

    assert actionizer.action(request=request) == expected
    assert expected.request is request
    assert expected.request_id == request.request_id
    assert DeterministicStructuredTranscriptionComposer is actionizer.__class__


def test__structured_transcription__preserves_golden_identity_and_bytes() -> (
    None
):
    _payload, request, result = _pipeline("born-digital-text")

    assert request.input_id == (
        "structured-transcription-input:sha256:"
        "b5e4354b306d5255eba51b7a1efea11ce0bb4ae776374bb0889f8788f587bef3"
    )
    assert result.result_id == (
        "structured-transcription-result:sha256:"
        "f7982a0bbb7f3c4bbcd8ec13282e21f52b523ea21b45070f85a0a0976591aded"
    )
    assert result.cache_key == (
        "structured-transcription-cache:sha256:"
        "00a8ee5d8f354c6f73a4d028974d6a8a3af6804745e42279c1097282307e91b0"
    )
    assert SHA256Verifier.verify(
        content=serialize_contract(result).encode("utf-8"),
        expected="a445d788ef02eb761792358d874cd321616035e5523be4c54f45fc05885834b3",
    )


def test__structured_transcription__is_deterministic_and_immutable() -> None:
    _payload, transcription_input, result = _pipeline("tables")
    repeated = DeterministicStructuredTranscriptionComposer().action(
        request=transcription_input
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
