from __future__ import annotations

import zlib
from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.ingestion import (
    DeterministicOCRReconciler,
    OCRReconciledItemKind,
    OCRReconciliationConfiguration,
    OCRReconciliationInput,
    OCRReconciliationLimitError,
    OCRReconciliationMatchKind,
    OCRReconciliationStreamChoice,
)
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedPage,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.ocr.models import (
    OCRConfidence,
    OCRConfiguration,
    OCRFailure,
    OCRFailureKind,
    OCRLanguageResourceIdentity,
    OCRLine,
    OCROutputMode,
    OCRPageImage,
    OcrProcessorIdentity,
    OcrRequest,
    OCRResourceIdentityKind,
    OcrResult,
    OCRSelection,
    OCRSelectionResult,
    OCRSelectionStatus,
    OCRWarning,
)
from projectkoios.ingestion.pdf.models import (
    RegionRenderConfiguration,
    RenderedRegion,
)

PROCESSOR_NAME = "synthetic-ocr-processor"
PROCESSOR_VERSION = "1"
BACKEND_NAME = "synthetic-ocr-backend"
BACKEND_VERSION = "1"


def _png(width: int = 100, height: int = 50) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + crc.to_bytes(4, "big")
        )

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes((8, 2, 0, 0, 0))
    )
    row = b"\x00" + b"\xff\xff\xff" * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def _processor_identity() -> OcrProcessorIdentity:
    return OcrProcessorIdentity(
        processor_name=PROCESSOR_NAME,
        processor_version=PROCESSOR_VERSION,
        backend_name=BACKEND_NAME,
        backend_version=BACKEND_VERSION,
        language_resources=(
            OCRLanguageResourceIdentity(
                language="und",
                resource_name="synthetic-und",
                identity_kind=OCRResourceIdentityKind.EXPLICIT,
                resource_identity="synthetic-und-v1",
            ),
        ),
    )


def _fixture(
    *,
    native: tuple[tuple[str, tuple[float, float, float, float]], ...],
    ocr: tuple[tuple[str, tuple[float, float, float, float]], ...],
    rotation: int = 0,
    status: OCRSelectionStatus = OCRSelectionStatus.COMPLETED,
) -> tuple[OcrResult, ExtractedPage | None, PageLayoutResult | None]:
    source = SourceDocument.from_bytes(
        b"synthetic-reconciliation-pdf" + bytes((rotation,)),
        source_id=f"document:reconciliation:{rotation}",
        media_type="application/pdf",
        locator="memory://reconciliation.pdf",
    )
    if rotation == 0:
        matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        effective = (0.0, 0.0, 100.0, 50.0)
        page_width = 100.0
        page_height = 50.0
    elif rotation == 90:
        matrix = (0.0, 1.0, -1.0, 0.0, 60.0, 10.0)
        effective = (10.0, 10.0, 60.0, 110.0)
        page_width = 120.0
        page_height = 120.0
    else:
        raise ValueError("unsupported synthetic rotation")
    region = RenderedRegion.create(
        source=source,
        page_index=0,
        printed_page_label="1",
        source_bounding_box=effective,
        effective_source_bounding_box=effective,
        pixel_to_source_matrix=matrix,
        page_rotation_degrees=rotation,
        selection_was_full_page=False,
        configuration=RegionRenderConfiguration(resolution_dpi=72),
        content=_png(),
        width_pixels=100,
        height_pixels=50,
        processor_name="synthetic-region-renderer",
        processor_version="1",
        backend_name="synthetic-pdf-backend",
        backend_version="1",
    )
    image = OCRPageImage.from_rendered_region(region)
    page: ExtractedPage | None
    layout: PageLayoutResult | None
    if native:
        blocks = tuple(
            ExtractedBlock(
                block_id=f"native:{index}",
                kind="text",
                source_spans=(
                    SourceSpan(
                        source_id=source.source_id,
                        source_blob_id=source.blob_id,
                        page_index=0,
                        bounding_box=box,
                    ),
                ),
                extraction_method="synthetic-native-text",
                confidence=1.0,
                text=text,
            )
            for index, (text, box) in enumerate(native)
        )
        page = ExtractedPage(
            page_index=0,
            width=page_width,
            height=page_height,
            blocks=blocks,
            coordinate_system=region.coordinate_system,
            rotation_degrees=rotation,
        )
        selection = OCRSelection.create(
            image,
            native_text_page=page,
            native_text_block_ids=tuple(block.block_id for block in blocks),
        )
        layout = DeterministicLayoutProcessor().analyze_page(source, page)
    else:
        page = None
        selection = OCRSelection.create(image)
        layout = None
    configuration = OCRConfiguration(output_mode=OCROutputMode.LINES)
    request = OcrRequest.create((selection,), configuration=configuration)
    lines = tuple(
        OCRLine.create(
            selection=selection,
            configuration=configuration,
            text=text,
            pixel_bounding_box=box,
            confidence=OCRConfidence(
                value=0.8,
                method="synthetic-score",
                method_version="1",
                scale="unit_interval",
            ),
            order=index,
            token_ids=(),
            processor_name=PROCESSOR_NAME,
            processor_version=PROCESSOR_VERSION,
            backend_name=BACKEND_NAME,
            backend_version=BACKEND_VERSION,
        )
        for index, (text, box) in enumerate(ocr)
    )
    warning = (
        OCRWarning.create(
            selection_id=selection.selection_id,
            code="ocr.synthetic_incomplete",
            severity=WarningSeverity.WARNING,
            message="Synthetic incomplete OCR output",
        )
        if status is not OCRSelectionStatus.COMPLETED
        else None
    )
    failure = (
        OCRFailure.create(
            selection_id=selection.selection_id,
            kind=OCRFailureKind.PROCESSOR_ERROR,
            message="Synthetic incomplete OCR execution",
            retryable=True,
            warning_ids=(warning.warning_id,),
        )
        if warning is not None
        else None
    )
    selection_result = OCRSelectionResult.create(
        selection=selection,
        configuration=configuration,
        status=status,
        lines=lines,
        warnings=(warning,) if warning is not None else (),
        failure=failure,
        processor_name=PROCESSOR_NAME,
        processor_version=PROCESSOR_VERSION,
        backend_name=BACKEND_NAME,
        backend_version=BACKEND_VERSION,
    )
    result = OcrResult.create(
        request=request,
        selection_results=(selection_result,),
        processor_identity=_processor_identity(),
    )
    return result, page, layout


def _reconcile(
    *,
    native: tuple[tuple[str, tuple[float, float, float, float]], ...],
    ocr: tuple[tuple[str, tuple[float, float, float, float]], ...],
    rotation: int = 0,
    status: OCRSelectionStatus = OCRSelectionStatus.COMPLETED,
    configuration: OCRReconciliationConfiguration | None = None,
):
    ocr_result, page, layout = _fixture(
        native=native,
        ocr=ocr,
        rotation=rotation,
        status=status,
    )
    reconciliation_input = OCRReconciliationInput.create(
        ocr_result=ocr_result,
        selection_index=0,
        native_page=page,
        layout_result=layout,
        configuration=configuration,
    )
    return DeterministicOCRReconciler().reconcile(reconciliation_input)


def test__reconciliation__preserves_duplicate_evidence_streams() -> None:
    result = _reconcile(
        native=(("Alpha beta", (5.0, 2.0, 80.0, 25.0)),),
        ocr=(("  alpha   BETA ", (5.0, 2.0, 80.0, 25.0)),),
    )

    assert len(result.matches) == 1
    assert result.matches[0].kind is OCRReconciliationMatchKind.DUPLICATE
    assert result.native_stream[0].text == "Alpha beta"
    assert result.ocr_stream[0].text == "  alpha   BETA "
    assert result.proposed_merged_stream[0].kind is (
        OCRReconciledItemKind.DUPLICATE
    )
    assert result.proposed_merged_stream[0].proposed_text == "Alpha beta"
    assert result.stream(OCRReconciliationStreamChoice.NATIVE) is (
        result.native_stream
    )
    assert result.stream(OCRReconciliationStreamChoice.OCR) is result.ocr_stream
    assert result.stream(
        OCRReconciliationStreamChoice.PROPOSED_MERGED
    ) is result.proposed_merged_stream


def test__reconciliation__rejects_conflicting_geometry() -> None:
    result = _reconcile(
        native=(("Repeated", (5.0, 2.0, 35.0, 15.0)),),
        ocr=(("Repeated", (60.0, 30.0, 90.0, 45.0)),),
    )

    assert not result.matches
    assert tuple(item.kind for item in result.proposed_merged_stream) == (
        OCRReconciledItemKind.NATIVE_ONLY,
        OCRReconciledItemKind.OCR_ONLY,
    )


def test__reconciliation__keeps_disagreement_unresolved() -> None:
    result = _reconcile(
        native=(("Alpha beta", (5.0, 2.0, 80.0, 25.0)),),
        ocr=(("Alpha zeta", (5.0, 2.0, 80.0, 25.0)),),
    )

    assert result.matches[0].kind is OCRReconciliationMatchKind.DISAGREEMENT
    item = result.proposed_merged_stream[0]
    assert item.kind is OCRReconciledItemKind.DISAGREEMENT
    assert item.proposed_text is None
    assert item.warning_ids == result.matches[0].warning_ids
    assert any(
        warning.code == "ocr.reconciliation.text_disagreement"
        for warning in result.warnings
    )


def test__reconciliation__represents_native_and_ocr_only_evidence() -> None:
    result = _reconcile(
        native=(("Native only", (5.0, 2.0, 35.0, 15.0)),),
        ocr=(("OCR only", (60.0, 30.0, 90.0, 45.0)),),
    )

    assert not result.matches
    assert tuple(item.kind for item in result.proposed_merged_stream) == (
        OCRReconciledItemKind.NATIVE_ONLY,
        OCRReconciledItemKind.OCR_ONLY,
    )
    assert tuple(
        item.proposed_text for item in result.proposed_merged_stream
    ) == ("Native only", "OCR only")
    assert result.proposed_merged_stream[1].warning_ids
    assert any(
        warning.code == "ocr.reconciliation.ocr_only_order_uncertain"
        for warning in result.warnings
    )


def test__reconciliation__projects_nonblank_native_lines_with_indices() -> None:
    result = _reconcile(
        native=(("Alpha\n\nBeta", (5.0, 2.0, 80.0, 25.0)),),
        ocr=(),
    )

    assert tuple(item.text for item in result.native_segments) == (
        "Alpha",
        "Beta",
    )
    assert tuple(item.line_index for item in result.native_segments) == (0, 2)


def test__reconciliation__uses_layout_order_for_native_stream() -> None:
    result = _reconcile(
        native=(
            ("Second", (5.0, 30.0, 80.0, 45.0)),
            ("First", (5.0, 2.0, 80.0, 15.0)),
        ),
        ocr=(),
    )

    assert tuple(item.text for item in result.native_stream) == (
        "First",
        "Second",
    )
    assert tuple(
        item.proposed_text for item in result.proposed_merged_stream
    ) == ("First", "Second")


def test__reconciliation__supports_blank_and_ocr_only_pages() -> None:
    native_only = _reconcile(
        native=(("Native text", (5.0, 2.0, 80.0, 25.0)),),
        ocr=(),
    )
    ocr_only = _reconcile(
        native=(),
        ocr=(("Image text", (5.0, 2.0, 80.0, 25.0)),),
    )
    blank = _reconcile(native=(), ocr=())

    assert native_only.proposed_merged_stream[0].kind is (
        OCRReconciledItemKind.NATIVE_ONLY
    )
    assert ocr_only.proposed_merged_stream[0].kind is (
        OCRReconciledItemKind.OCR_ONLY
    )
    assert not blank.native_stream
    assert not blank.ocr_stream
    assert not blank.proposed_merged_stream


def test__reconciliation__retains_partial_and_failed_ocr_outcomes() -> None:
    box = (5.0, 2.0, 80.0, 25.0)
    partial = _reconcile(
        native=(("Partial text", box),),
        ocr=(("Partial text", box),),
        status=OCRSelectionStatus.PARTIAL,
    )
    failed = _reconcile(
        native=(("Native fallback", box),),
        ocr=(),
        status=OCRSelectionStatus.FAILED,
    )

    assert partial.matches[0].kind is OCRReconciliationMatchKind.DUPLICATE
    assert partial.reconciliation_input.selection_result.failure is not None
    assert failed.proposed_merged_stream[0].kind is (
        OCRReconciledItemKind.NATIVE_ONLY
    )
    assert failed.reconciliation_input.selection_result.failure is not None
    for result in (partial, failed):
        assert any(
            warning.code == "ocr.reconciliation.incomplete_ocr_stream"
            for warning in result.warnings
        )


def test__reconciliation__marks_equal_competing_matches_ambiguous() -> None:
    box = (5.0, 2.0, 80.0, 25.0)
    result = _reconcile(
        native=(("Repeated", box), ("Repeated", box)),
        ocr=(("Repeated", box),),
    )

    assert not result.matches
    assert tuple(item.kind for item in result.proposed_merged_stream) == (
        OCRReconciledItemKind.NATIVE_ONLY,
        OCRReconciledItemKind.NATIVE_ONLY,
        OCRReconciledItemKind.OCR_ONLY,
    )
    assert any(
        warning.code == "ocr.reconciliation.ambiguous_match"
        for warning in result.warnings
    )


def test__reconciliation__uses_source_geometry_on_rotated_pages() -> None:
    result = _reconcile(
        native=(("Rotated", (40.0, 15.0, 58.0, 55.0)),),
        ocr=(("Rotated", (5.0, 2.0, 45.0, 20.0)),),
        rotation=90,
    )

    assert result.matches[0].kind is OCRReconciliationMatchKind.DUPLICATE
    assert result.matches[0].geometry_overlap == 1.0


def test__reconciliation__is_deterministic_and_immutable() -> None:
    native = (("Alpha", (5.0, 2.0, 80.0, 25.0)),)
    ocr = (("Alpha", (5.0, 2.0, 80.0, 25.0)),)
    first = _reconcile(native=native, ocr=ocr)
    second = _reconcile(native=native, ocr=ocr)

    assert first == second
    assert first.result_id == second.result_id
    with pytest.raises(FrozenInstanceError):
        first.result_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="inconsistent"):
        replace(first, result_id="changed")


def test__reconciliation__rejects_stale_native_page() -> None:
    ocr_result, page, layout = _fixture(
        native=(("Alpha", (5.0, 2.0, 80.0, 25.0)),),
        ocr=(("Alpha", (5.0, 2.0, 80.0, 25.0)),),
    )
    assert page is not None
    stale_page = replace(page, width=page.width + 1.0)

    with pytest.raises(ValueError, match="native page"):
        OCRReconciliationInput.create(
            ocr_result=ocr_result,
            selection_index=0,
            native_page=stale_page,
            layout_result=layout,
        )


def test__reconciliation__retains_text_skipped_by_comparison_limit() -> None:
    box = (5.0, 2.0, 80.0, 25.0)
    result = _reconcile(
        native=(("Long native evidence", box),),
        ocr=(("Long native evidence", box),),
        configuration=OCRReconciliationConfiguration(
            max_comparison_text_characters=5
        ),
    )

    assert not result.matches
    assert tuple(item.kind for item in result.proposed_merged_stream) == (
        OCRReconciledItemKind.NATIVE_ONLY,
        OCRReconciledItemKind.OCR_ONLY,
    )
    assert result.native_stream[0].text == "Long native evidence"
    assert result.ocr_stream[0].text == "Long native evidence"
    assert any(
        warning.code == "ocr.reconciliation.text_comparison_skipped"
        for warning in result.warnings
    )


def test__reconciliation__rejects_pair_count_before_matching() -> None:
    result, page, layout = _fixture(
        native=(
            ("Alpha", (5.0, 2.0, 30.0, 20.0)),
            ("Beta", (35.0, 2.0, 60.0, 20.0)),
        ),
        ocr=(
            ("Alpha", (5.0, 2.0, 30.0, 20.0)),
            ("Beta", (35.0, 2.0, 60.0, 20.0)),
        ),
    )
    reconciliation_input = OCRReconciliationInput.create(
        ocr_result=result,
        selection_index=0,
        native_page=page,
        layout_result=layout,
        configuration=OCRReconciliationConfiguration(max_candidate_pairs=3),
    )

    with pytest.raises(OCRReconciliationLimitError, match="candidate pairs"):
        DeterministicOCRReconciler().reconcile(reconciliation_input)
