from io import BytesIO
from typing import BinaryIO

import pytest
from projectkoios.ingestion import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    PdfArticleIngester,
    PdfTextbookIngester,
    SourceDocument,
    SourceSpan,
    StructureAnalysis,
    StructureKind,
    StructureNode,
)

PDF_BYTES = b"generated PDF fixture"


def make_source(
    *,
    source_id: str = "document:fixture",
    media_type: str = "application/pdf",
) -> SourceDocument:
    return SourceDocument.from_bytes(
        PDF_BYTES,
        source_id=source_id,
        media_type=media_type,
        locator="memory://fixture.pdf",
    )


def make_extraction(source: SourceDocument) -> ExtractionResult:
    span = SourceSpan(
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        page_index=0,
        source_object_id="text-1",
        bounding_box=(10.0, 10.0, 500.0, 100.0),
    )
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(span,),
        extraction_method="fixture",
        confidence=1.0,
        text="Chapter 1: Introduction",
    )
    page = ExtractedPage(
        page_index=0,
        width=612.0,
        height=792.0,
        blocks=(block,),
    )
    document = ExtractedDocument.create(
        source=source,
        pages=(page,),
        metadata=(("title", "Fixture Document"),),
    )
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="fixture",
        extractor_version="1.0",
        configuration_digest="sha256:fixture",
        object_ids=(document.document_id,),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-01-01T00:00:00Z",
    )
    return ExtractionResult(document=document, manifest=manifest)


class FakeExtractor:
    name = "fixture"
    version = "1.0"

    def __init__(self) -> None:
        self.called = False

    def extract(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult:
        self.called = True
        assert content.read() == PDF_BYTES
        return make_extraction(source)


class ChapterAnalyzer:
    def analyze(self, document: ExtractedDocument) -> StructureAnalysis:
        span = document.pages[0].blocks[0].source_spans[0]
        chapter = StructureNode.create(
            kind=StructureKind.CHAPTER,
            source_spans=(span,),
            evidence_type="numbered_heading",
            confidence=0.95,
            label="1",
            title="Introduction",
        )
        return StructureAnalysis(nodes=(chapter,))


def test__pdf_article_ingester__returns_article() -> None:
    source = make_source(source_id="article:fixture")
    extractor = FakeExtractor()
    ingester = PdfArticleIngester(extractor, ChapterAnalyzer())

    article = ingester.ingest(source, BytesIO(PDF_BYTES))

    assert article.extraction.document.source == source
    assert article.structure.nodes[0].kind is StructureKind.CHAPTER
    assert article.bibliographic_candidates == (("title", "Fixture Document"),)


def test__pdf_textbook_ingester__returns_structured_textbook() -> None:
    source = make_source(source_id="textbook:fixture")
    extractor = FakeExtractor()
    ingester = PdfTextbookIngester(extractor, ChapterAnalyzer())

    textbook = ingester.ingest(source, BytesIO(PDF_BYTES))

    assert textbook.extraction.document.source == source
    assert textbook.structure.nodes[0].label == "1"
    assert textbook.structure.nodes[0].title == "Introduction"


def test__pdf_ingester__rejects_non_pdf_before_extraction() -> None:
    source = make_source(media_type="text/plain")
    extractor = FakeExtractor()
    ingester = PdfTextbookIngester(extractor, ChapterAnalyzer())

    with pytest.raises(ValueError, match="application/pdf"):
        ingester.ingest(source, BytesIO(PDF_BYTES))

    assert extractor.called is False


def test__structure_analysis__requires_reciprocal_hierarchy() -> None:
    source = make_source()
    document = make_extraction(source).document
    span = document.pages[0].blocks[0].source_spans[0]
    parent = StructureNode.create(
        kind=StructureKind.CHAPTER,
        source_spans=(span,),
        evidence_type="bookmark",
        confidence=1.0,
    )
    child = StructureNode.create(
        kind=StructureKind.SECTION,
        source_spans=(span,),
        evidence_type="numbered_heading",
        confidence=0.9,
        parent_id=parent.node_id,
        label="1.1",
    )

    with pytest.raises(ValueError, match="reciprocal"):
        StructureAnalysis(nodes=(parent, child))


def test__specialized_document__rejects_structure_from_another_blob() -> None:
    source = make_source(source_id="textbook:fixture")
    extraction = make_extraction(source)
    other_source = SourceDocument.from_bytes(
        b"different bytes",
        source_id=source.source_id,
        media_type="application/pdf",
        locator="memory://other.pdf",
    )
    other_document = make_extraction(other_source).document
    bad_structure = ChapterAnalyzer().analyze(other_document)
    ingester = PdfTextbookIngester(FakeExtractor(), ChapterAnalyzer())

    textbook = ingester.ingest(source, BytesIO(PDF_BYTES))

    with pytest.raises(ValueError, match="exact extracted source"):
        type(textbook)(
            extraction=extraction,
            structure=bad_structure,
        )
