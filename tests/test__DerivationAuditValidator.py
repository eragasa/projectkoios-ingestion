from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    CleanTranscriptArtifact,
    CleanTranscriptBlock,
    CleanTranscriptExclusion,
    CleanTranscriptExclusionReason,
    CleanTranscriptPage,
    DeterministicArticleStructureAnalyzer,
    DeterministicCleanTranscriptProjector,
    DeterministicEquationCandidateDetector,
    DeterministicFigureCandidateDetector,
    DeterministicOCRReconciler,
    DeterministicStructuredTranscriptionComposer,
    DeterministicTableCandidateDetector,
    DeterministicTableStructureReconstructor,
    OCRConfiguration,
    OCRLanguageResourceIdentity,
    OCRLine,
    OCRPageImage,
    OcrProcessorIdentity,
    OCRReconciliationInput,
    OCRReconciliationResult,
    OcrRequest,
    OCRResourceIdentityKind,
    OcrResult,
    OCRSelection,
    OCRSelectionResult,
    OCRSelectionStatus,
    OCRToken,
    PyMuPdfExtractor,
    TranscriptionInput,
)
from projectkoios.ingestion import (
    DerivationAuditValidator as PublicDerivationAuditValidator,
)
from projectkoios.ingestion.article_structure import (
    ARTICLE_STRUCTURE_PROCESSOR_VERSION,
)
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.pdf import PYMUPDF_COORDINATE_SYSTEM
from projectkoios.ingestion.processing import (
    BoundedProcessingCoordinator,
    ProcessingDerivedArtifact,
    ProcessingInvocationResult,
    ProcessingPhysicalPageRange,
    ProcessingProcessorIdentity,
    ProcessingRequest,
    ProcessingResourceIdentity,
    ProcessingResourceIdentityKind,
    ProcessingSelection,
    ProcessingStatus,
    ProcessingWorkItem,
)
from projectkoios.ingestion.provenance import (
    DerivationAuditError,
    DerivationAuditFindingCode,
    DerivationAuditInput,
    DerivationAuditLimitError,
    DerivationAuditStatus,
    DerivationAuditValidator,
)
from projectkoios.ingestion.structure import StructureAnalysis

pymupdf = pytest.importorskip("pymupdf")
FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


def _fixture() -> tuple[bytes, ExtractionResult, PageLayoutResult]:
    content = b"%PDF-1.7\nprovenance-fixture\n%%EOF\n"
    source = SourceDocument.from_bytes(
        content,
        source_id="fixture:provenance",
        media_type="application/pdf",
        locator="fixture://provenance.pdf",
    )
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                source_object_id="page:0:block:0",
                bounding_box=(10.0, 10.0, 90.0, 20.0),
            ),
        ),
        extraction_method="fixture-extractor",
        confidence=1.0,
        text="A complete source block.",
    )
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=(block,),
        coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
    )
    document = ExtractedDocument.create(source=source, pages=(page,))
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="fixture-extractor",
        extractor_version="1",
        configuration_digest="fixture-configuration",
        object_ids=(document.document_id, block.block_id),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-09-17T00:00:00Z",
        completed_at="2026-09-17T00:00:00Z",
    )
    extraction = ExtractionResult(document=document, manifest=manifest)
    layout = DeterministicLayoutProcessor().analyze(document)[0]
    return content, extraction, layout


def _codes(report) -> set[DerivationAuditFindingCode]:
    return {finding.code for finding in report.findings}


class _AuditProcessor:
    name = "fixture-audit-processor"
    version = "1"

    def identity_for(
        self, _work_item: ProcessingWorkItem
    ) -> ProcessingProcessorIdentity:
        return ProcessingProcessorIdentity(
            processor_name=self.name,
            processor_version=self.version,
            backend_name="fixture-backend",
            backend_version="1",
            configuration_digest="fixture-audit-processor-v1",
            resources=(
                ProcessingResourceIdentity(
                    resource_name="fixture-model",
                    identity_kind=ProcessingResourceIdentityKind.EXPLICIT,
                    resource_identity="fixture-model-v1",
                ),
            ),
        )

    def process(
        self, work_item: ProcessingWorkItem
    ) -> ProcessingInvocationResult:
        identity = self.identity_for(work_item)
        artifact = ProcessingDerivedArtifact.create(
            work_item=work_item,
            artifact_kind="fixture-derived-evidence",
            media_type="application/octet-stream",
            content=b"derived evidence",
            input_object_ids=work_item.input_object_ids,
            source_spans=work_item.source_spans,
        )
        return ProcessingInvocationResult.create(
            work_item=work_item,
            processor_identity=identity,
            status=ProcessingStatus.COMPLETED,
            artifacts=(artifact,),
        )


@dataclass(frozen=True)
class _CleanAuditFixture:
    content: bytes
    extraction: ExtractionResult
    layouts: tuple[PageLayoutResult, ...]
    structure: StructureAnalysis
    equations: object
    table_detection: object
    table_structure: object
    figures: object
    transcription: object
    clean: CleanTranscriptArtifact

    def audit(self, clean: CleanTranscriptArtifact) -> object:
        return DerivationAuditValidator().audit(
            DerivationAuditInput(
                source_content=self.content,
                extraction_result=self.extraction,
                layout_results=self.layouts,
                structure_analyses=(self.structure,),
                equation_results=(self.equations,),
                table_detection_results=(self.table_detection,),
                table_structure_results=(self.table_structure,),
                figure_results=(self.figures,),
                transcription_results=(self.transcription,),
                clean_transcript_artifacts=(clean,),
            )
        )


@pytest.fixture(scope="module")
def clean_audit_fixture() -> _CleanAuditFixture:
    pdf = pymupdf.open()
    for page_index in range(3):
        page = pdf.new_page(width=420, height=420)
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
    content = pdf.tobytes()
    pdf.close()
    source = SourceDocument.from_bytes(
        content,
        source_id="fixture:provenance:clean",
        media_type="application/pdf",
        locator="fixture://clean.pdf",
    )
    extraction = PyMuPdfExtractor().extract(source, BytesIO(content))
    document = extraction.document
    layouts = DeterministicLayoutProcessor().analyze(document)
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    equations = DeterministicEquationCandidateDetector().detect_with_layout(
        document, BytesIO(content), layouts
    )
    table_detection = DeterministicTableCandidateDetector().detect_with_layout(
        document, BytesIO(content), layouts
    )
    table_structure = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector().detect_with_layout(
        document, BytesIO(content), layouts
    )
    transcription = DeterministicStructuredTranscriptionComposer().compose(
        TranscriptionInput.create(
            document=document,
            structure_analysis=structure,
            equation_detection_result=equations,
            table_structure_result=table_structure,
            figure_detection_result=figures,
        )
    )
    clean = DeterministicCleanTranscriptProjector().project(
        transcription, layouts
    )
    assert clean.blocks
    assert clean.exclusions
    return _CleanAuditFixture(
        content=content,
        extraction=extraction,
        layouts=layouts,
        structure=structure,
        equations=equations,
        table_detection=table_detection,
        table_structure=table_structure,
        figures=figures,
        transcription=transcription,
        clean=clean,
    )


def _rebuild_clean(
    fixture: _CleanAuditFixture,
    *,
    blocks: tuple[CleanTranscriptBlock, ...] | None = None,
    exclusions: tuple[CleanTranscriptExclusion, ...] | None = None,
) -> CleanTranscriptArtifact:
    original = fixture.clean
    retained_blocks = original.blocks if blocks is None else blocks
    retained_exclusions = (
        original.exclusions if exclusions is None else exclusions
    )
    pages: list[CleanTranscriptPage] = []
    for root_page in fixture.extraction.document.pages:
        page_blocks = tuple(
            sorted(
                (
                    block
                    for block in retained_blocks
                    if block.page_index == root_page.page_index
                ),
                key=lambda block: block.order_index,
            )
        )
        label = (
            "none"
            if root_page.printed_page_label is None
            else root_page.printed_page_label.replace('"', "'")
        )
        marker = (
            f'[[PAGE physical={root_page.page_index + 1} printed="{label}"]]'
        )
        body = "\n\n".join(block.clean_text for block in page_blocks)
        page_text = marker if not body else f"{marker}\n\n{body}"
        pages.append(
            CleanTranscriptPage.create(
                page_index=root_page.page_index,
                printed_page_label=root_page.printed_page_label,
                block_record_ids=tuple(
                    block.record_id for block in page_blocks
                ),
                text=page_text,
            )
        )
    text = "\n\n".join(page.text for page in pages) + "\n"
    return CleanTranscriptArtifact.create(
        transcription_result=fixture.transcription,
        layouts=fixture.layouts,
        pages=tuple(pages),
        blocks=retained_blocks,
        exclusions=retained_exclusions,
        text=text,
        warnings=original.warnings,
        processor_name=original.processor_name,
        processor_version=original.processor_version,
        configuration_digest=original.configuration_digest,
    )


def _recreate_block(
    block: CleanTranscriptBlock,
    *,
    page_index: int | None = None,
    printed_page_label: str | None = None,
    order_index: int | None = None,
) -> CleanTranscriptBlock:
    return CleanTranscriptBlock.create(
        block_id=block.block_id,
        page_index=block.page_index if page_index is None else page_index,
        printed_page_label=(
            block.printed_page_label
            if printed_page_label is None
            else printed_page_label
        ),
        order_index=(block.order_index if order_index is None else order_index),
        raw_text=block.raw_text,
        clean_text=block.clean_text,
        source_spans=block.source_spans,
        transformations=block.transformations,
    )


def _recreate_exclusion(
    exclusion: CleanTranscriptExclusion,
    *,
    printed_page_label: str,
) -> CleanTranscriptExclusion:
    return CleanTranscriptExclusion.create(
        block_id=exclusion.block_id,
        page_index=exclusion.page_index,
        printed_page_label=printed_page_label,
        reason=exclusion.reason,
        raw_text=exclusion.raw_text,
        source_spans=exclusion.source_spans,
    )


def test__derivation_audit__public_export_is_available() -> None:
    assert PublicDerivationAuditValidator is DerivationAuditValidator


def test__derivation_audit__accepts_complete_clean_partition(
    clean_audit_fixture: _CleanAuditFixture,
) -> None:
    report = clean_audit_fixture.audit(clean_audit_fixture.clean)

    assert report.status is DerivationAuditStatus.PASSED, report.findings
    assert report.findings == ()


def test__clean_transcript_identity__binds_printed_page_labels(
    clean_audit_fixture: _CleanAuditFixture,
) -> None:
    clean = clean_audit_fixture.clean

    with pytest.raises(ValueError, match="block ID is inconsistent"):
        replace(clean.blocks[0], printed_page_label="tampered-label")
    with pytest.raises(ValueError, match="exclusion ID is inconsistent"):
        replace(clean.exclusions[0], printed_page_label="tampered-label")


@pytest.mark.parametrize("record_kind", ("block", "exclusion"))
def test__derivation_audit__rejects_changed_clean_printed_page_label(
    clean_audit_fixture: _CleanAuditFixture,
    record_kind: str,
) -> None:
    clean = clean_audit_fixture.clean
    if record_kind == "block":
        tampered = _recreate_block(
            clean.blocks[0], printed_page_label="tampered-label"
        )
        blocks = (tampered, *clean.blocks[1:])
        artifact = _rebuild_clean(clean_audit_fixture, blocks=blocks)
    else:
        tampered = _recreate_exclusion(
            clean.exclusions[0], printed_page_label="tampered-label"
        )
        exclusions = (tampered, *clean.exclusions[1:])
        artifact = _rebuild_clean(clean_audit_fixture, exclusions=exclusions)

    report = clean_audit_fixture.audit(artifact)

    assert report.status is DerivationAuditStatus.FAILED
    assert DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH in _codes(
        report
    )


@pytest.mark.parametrize("record_kind", ("block", "exclusion"))
def test__derivation_audit__rejects_omitted_clean_partition_record(
    clean_audit_fixture: _CleanAuditFixture,
    record_kind: str,
) -> None:
    clean = clean_audit_fixture.clean
    if record_kind == "block":
        artifact = _rebuild_clean(clean_audit_fixture, blocks=clean.blocks[1:])
    else:
        artifact = _rebuild_clean(
            clean_audit_fixture, exclusions=clean.exclusions[1:]
        )

    report = clean_audit_fixture.audit(artifact)

    assert report.status is DerivationAuditStatus.FAILED
    assert DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING in _codes(
        report
    )


def test__derivation_audit__rejects_zero_clean_partition_coverage(
    clean_audit_fixture: _CleanAuditFixture,
) -> None:
    artifact = _rebuild_clean(clean_audit_fixture, blocks=(), exclusions=())

    report = clean_audit_fixture.audit(artifact)

    assert report.status is DerivationAuditStatus.FAILED
    assert DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING in _codes(
        report
    )


@pytest.mark.parametrize("duplicate_kind", ("included", "cross_class"))
def test__derivation_audit__rejects_duplicate_clean_partition_coverage(
    clean_audit_fixture: _CleanAuditFixture,
    duplicate_kind: str,
) -> None:
    clean = clean_audit_fixture.clean
    if duplicate_kind == "included":
        artifact = _rebuild_clean(
            clean_audit_fixture,
            blocks=(*clean.blocks, clean.blocks[0]),
        )
    else:
        record = clean.blocks[0]
        duplicate = CleanTranscriptExclusion.create(
            block_id=record.block_id,
            page_index=record.page_index,
            printed_page_label=record.printed_page_label,
            reason=CleanTranscriptExclusionReason.EMPTY_AFTER_SANITIZATION,
            raw_text=record.raw_text,
            source_spans=record.source_spans,
        )
        artifact = _rebuild_clean(
            clean_audit_fixture,
            exclusions=(*clean.exclusions, duplicate),
        )

    report = clean_audit_fixture.audit(artifact)

    assert report.status is DerivationAuditStatus.FAILED
    assert DerivationAuditFindingCode.DUPLICATE_OBJECT_ID in _codes(report)


def test__derivation_audit__rejects_cross_page_clean_block(
    clean_audit_fixture: _CleanAuditFixture,
) -> None:
    clean = clean_audit_fixture.clean
    first = clean.blocks[0]
    target_page = clean_audit_fixture.extraction.document.pages[1]
    tampered = _recreate_block(
        first,
        page_index=target_page.page_index,
        printed_page_label=target_page.printed_page_label,
    )
    artifact = _rebuild_clean(
        clean_audit_fixture, blocks=(tampered, *clean.blocks[1:])
    )

    report = clean_audit_fixture.audit(artifact)

    assert report.status is DerivationAuditStatus.FAILED
    assert DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH in _codes(
        report
    )


def test__derivation_audit__rejects_clean_block_order_tampering(
    clean_audit_fixture: _CleanAuditFixture,
) -> None:
    clean = clean_audit_fixture.clean
    page_zero = tuple(
        (index, block)
        for index, block in enumerate(clean.blocks)
        if block.page_index == 0
    )
    assert len(page_zero) >= 2
    (left_index, left), (right_index, right) = page_zero[:2]
    replacements = {
        left_index: _recreate_block(left, order_index=right.order_index),
        right_index: _recreate_block(right, order_index=left.order_index),
    }
    blocks = tuple(
        replacements.get(index, block)
        for index, block in enumerate(clean.blocks)
    )
    artifact = _rebuild_clean(clean_audit_fixture, blocks=blocks)

    report = clean_audit_fixture.audit(artifact)

    assert report.status is DerivationAuditStatus.FAILED
    assert DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH in _codes(
        report
    )


def test__derivation_audit__accepts_exact_raw_and_layout_provenance() -> None:
    content, extraction, layout = _fixture()
    audit_input = DerivationAuditInput(
        source_content=content,
        extraction_result=extraction,
        layout_results=(layout,),
    )
    validator = DerivationAuditValidator()

    first = validator.audit(audit_input)
    second = validator.audit(audit_input)

    assert first == second
    assert first.status is DerivationAuditStatus.PASSED
    assert first.valid
    assert first.findings == ()
    assert ("layout_results", "1") in first.audited_layer_counts
    first.require_valid()
    validator.validate(audit_input)


@pytest.mark.parametrize("fixture_name", ("equations", "tables", "figures"))
def test__derivation_audit__accepts_complete_structured_pipeline(
    fixture_name: str,
) -> None:
    content = (FIXTURES / f"{fixture_name}.pdf").read_bytes()
    source = SourceDocument.from_bytes(
        content,
        source_id=f"fixture:provenance:complete:{fixture_name}",
        media_type="application/pdf",
        locator=f"fixture://{fixture_name}.pdf",
    )
    extraction = PyMuPdfExtractor().extract(source, BytesIO(content))
    document = extraction.document
    layouts = DeterministicLayoutProcessor().analyze(document)
    structure = DeterministicArticleStructureAnalyzer().analyze(document)
    equations = DeterministicEquationCandidateDetector().detect_with_layout(
        document, BytesIO(content), layouts
    )
    table_detection = DeterministicTableCandidateDetector().detect_with_layout(
        document, BytesIO(content), layouts
    )
    table_structure = DeterministicTableStructureReconstructor().reconstruct(
        table_detection
    )
    figures = DeterministicFigureCandidateDetector().detect_with_layout(
        document, BytesIO(content), layouts
    )
    transcription = DeterministicStructuredTranscriptionComposer().compose(
        TranscriptionInput.create(
            document=document,
            structure_analysis=structure,
            equation_detection_result=equations,
            table_structure_result=table_structure,
            figure_detection_result=figures,
        )
    )
    ocr_results: tuple[OcrResult, ...] = ()
    reconciliation_results: tuple[OCRReconciliationResult, ...] = ()
    if equations.candidates:
        candidate = equations.candidates[0]
        image = OCRPageImage.from_rendered_region(candidate.rendered_region)
        selection = OCRSelection.create(
            image,
            native_text_page=document.pages[
                candidate.rendered_region.page_index
            ],
            native_text_block_ids=(candidate.source_block_id,),
        )
        configuration = OCRConfiguration()
        processor_name = "fixture-ocr"
        processor_version = "1"
        backend_name = "fixture-backend"
        backend_version = "1"
        token = OCRToken.create(
            selection=selection,
            configuration=configuration,
            text="x",
            pixel_bounding_box=(0.0, 0.0, 1.0, 1.0),
            confidence=None,
            order=0,
            line_order=0,
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )
        line = OCRLine.create(
            selection=selection,
            configuration=configuration,
            text="x",
            pixel_bounding_box=(0.0, 0.0, 1.0, 1.0),
            confidence=None,
            order=0,
            token_ids=(token.token_id,),
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )
        request = OcrRequest.create((selection,), configuration=configuration)
        selection_result = OCRSelectionResult.create(
            selection=selection,
            configuration=configuration,
            status=OCRSelectionStatus.COMPLETED,
            tokens=(token,),
            lines=(line,),
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
        )
        identity = OcrProcessorIdentity(
            processor_name=processor_name,
            processor_version=processor_version,
            backend_name=backend_name,
            backend_version=backend_version,
            language_resources=(
                OCRLanguageResourceIdentity(
                    language="und",
                    resource_name="fixture-language",
                    identity_kind=OCRResourceIdentityKind.EXPLICIT,
                    resource_identity="fixture-language-v1",
                ),
            ),
        )
        ocr_results = (
            OcrResult.create(
                request=request,
                selection_results=(selection_result,),
                processor_identity=identity,
            ),
        )
        reconciliation_results = (
            DeterministicOCRReconciler().reconcile(
                OCRReconciliationInput.create(
                    ocr_result=ocr_results[0],
                    selection_index=0,
                    native_page=document.pages[
                        candidate.rendered_region.page_index
                    ],
                    layout_result=layouts[candidate.rendered_region.page_index],
                )
            ),
        )

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=content,
            extraction_result=extraction,
            ocr_results=ocr_results,
            reconciliation_results=reconciliation_results,
            layout_results=layouts,
            structure_analyses=(structure,),
            equation_results=(equations,),
            table_detection_results=(table_detection,),
            table_structure_results=(table_structure,),
            figure_results=(figures,),
            transcription_results=(transcription,),
        )
    )

    assert report.status is DerivationAuditStatus.PASSED, report.findings
    assert report.findings == ()


def test__derivation_audit__accepts_bounded_processing_provenance() -> None:
    content, extraction, _layout = _fixture()
    selection = ProcessingSelection.create(
        document=extraction.document,
        physical_page_ranges=(
            ProcessingPhysicalPageRange.create(
                start_page_index=0,
                end_page_index=0,
            ),
        ),
    )
    processing = BoundedProcessingCoordinator(_AuditProcessor()).process(
        ProcessingRequest.create(selections=(selection,))
    )

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=content,
            extraction_result=extraction,
            processing_results=(processing,),
        )
    )

    assert report.status is DerivationAuditStatus.PASSED, report.findings


def test__derivation_audit__rejects_wrong_source_blob() -> None:
    content, extraction, layout = _fixture()
    object.__setattr__(layout, "source_blob_id", "blob:sha256:" + "0" * 64)

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=content,
            extraction_result=extraction,
            layout_results=(layout,),
        )
    )

    assert report.status is DerivationAuditStatus.FAILED
    assert DerivationAuditFindingCode.SOURCE_BLOB_MISMATCH in _codes(report)


def test__derivation_audit__rejects_orphan_derived_reference() -> None:
    content, extraction, layout = _fixture()
    object.__setattr__(layout, "raw_block_ids", ("block:missing",))

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=content,
            extraction_result=extraction,
            layout_results=(layout,),
        )
    )

    assert DerivationAuditFindingCode.ORPHAN_OBJECT_REFERENCE in _codes(report)


def test__derivation_audit__rejects_out_of_range_source_region() -> None:
    content, extraction, layout = _fixture()
    span = extraction.document.pages[0].blocks[0].source_spans[0]
    object.__setattr__(span, "bounding_box", (10.0, 10.0, 110.0, 20.0))

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=content,
            extraction_result=extraction,
            layout_results=(layout,),
        )
    )

    assert DerivationAuditFindingCode.REGION_OUT_OF_RANGE in _codes(report)


def test__derivation_audit__rejects_missing_processor_version() -> None:
    content, extraction, layout = _fixture()
    object.__setattr__(layout, "processor_version", "")
    audit_input = DerivationAuditInput(
        source_content=content,
        extraction_result=extraction,
        layout_results=(layout,),
    )

    report = DerivationAuditValidator().audit(audit_input)

    assert DerivationAuditFindingCode.PROCESSOR_IDENTITY_MISSING in _codes(
        report
    )
    try:
        report.require_valid()
    except DerivationAuditError as error:
        assert error.report == report
    else:
        raise AssertionError("invalid audit report was accepted")


def test__derivation_audit__rejects_unregistered_transitive_upstream() -> None:
    content, extraction, layout = _fixture()
    analysis = StructureAnalysis.create(
        source=extraction.document.source,
        nodes=(),
        warnings=(),
        layout_result_ids=(layout.result_id,),
        input_block_ids=(extraction.document.pages[0].blocks[0].block_id,),
        processor_name="deterministic-article-structure",
        processor_version=ARTICLE_STRUCTURE_PROCESSOR_VERSION,
        configuration_digest="fixture-structure-configuration",
    )

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=content,
            extraction_result=extraction,
            structure_analyses=(analysis,),
        )
    )

    assert DerivationAuditFindingCode.ORPHAN_OBJECT_REFERENCE in _codes(report)


def test__derivation_audit__bounds_artifacts_per_layer() -> None:
    content, extraction, layout = _fixture()

    with pytest.raises(DerivationAuditLimitError, match="layout_results"):
        DerivationAuditInput(
            source_content=content,
            extraction_result=extraction,
            layout_results=(layout,) * 4_097,
        )


def test__derivation_audit__rejects_wrong_source_bytes() -> None:
    _, extraction, _ = _fixture()

    report = DerivationAuditValidator().audit(
        DerivationAuditInput(
            source_content=b"different source bytes",
            extraction_result=extraction,
        )
    )

    assert DerivationAuditFindingCode.SOURCE_CONTENT_MISMATCH in _codes(report)
