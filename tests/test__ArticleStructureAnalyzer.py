from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    ArticleStructureConfiguration,
    ArticleStructureLimitError,
    DeterministicArticleStructureAnalyzer,
    DeterministicLayoutProcessor,
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    PyMuPdfExtractor,
    SourceDocument,
    SourceSpan,
    StructureEvidenceStatus,
    StructureKind,
    TableOfContentsEntry,
)


def _document(
    texts: tuple[str, ...],
    *,
    source_bytes: bytes = b"synthetic-article",
    metadata_title: str | None = "A Deterministic Article",
    with_toc: bool = False,
) -> ExtractedDocument:
    source = SourceDocument.from_bytes(
        source_bytes,
        source_id="article:synthetic",
        media_type="application/pdf",
        locator="memory://article.pdf",
    )
    blocks = tuple(
        ExtractedBlock.create(
            kind="text",
            source_spans=(
                SourceSpan(
                    source_id=source.source_id,
                    source_blob_id=source.blob_id,
                    page_index=0,
                    source_object_id=f"text:{index}",
                    bounding_box=(
                        40.0,
                        20.0 + index * 45.0,
                        560.0,
                        45.0 + index * 45.0,
                    ),
                ),
            ),
            extraction_method="synthetic",
            confidence=0.99,
            text=text,
        )
        for index, text in enumerate(texts)
    )
    page = ExtractedPage(
        page_index=0,
        width=600.0,
        height=max(800.0, 80.0 + len(blocks) * 45.0),
        blocks=blocks,
        coordinate_system="pymupdf_unrotated_cropbox_points_top_left",
    )
    table_of_contents: tuple[TableOfContentsEntry, ...] = ()
    if with_toc:
        introduction = next(
            block for block in blocks if block.text == "1 Introduction"
        )
        table_of_contents = (
            TableOfContentsEntry.create(
                source=source,
                level=1,
                title="Introduction",
                destination=introduction.source_spans[0],
                source_object_id="toc:1",
            ),
        )
    return ExtractedDocument.create(
        source=source,
        pages=(page,),
        metadata=(
            (("title", metadata_title),) if metadata_title is not None else ()
        ),
        table_of_contents=table_of_contents,
    )


def _analyze(document: ExtractedDocument):
    layouts = DeterministicLayoutProcessor().analyze(document)
    return DeterministicArticleStructureAnalyzer().analyze_with_layout(
        document, layouts
    )


def test__article_structure__detects_bounded_article_hierarchy() -> None:
    document = _document(
        (
            "A Deterministic Article",
            "Authors: Ada Lovelace and Emmy Noether",
            "Abstract",
            "We describe a deterministic method.",
            "Keywords: determinism; evidence",
            "1 Introduction",
            "Introductory prose.",
            "1.1 Context",
            "Context prose.",
            "References",
            "[1] A. Author. An observed reference.",
            "Appendix A Supplemental Proof",
        ),
        with_toc=True,
    )

    result = _analyze(document)
    kinds = tuple(node.kind for node in result.nodes)

    assert StructureKind.DOCUMENT in kinds
    assert StructureKind.FRONT_MATTER in kinds
    assert StructureKind.TITLE in kinds
    assert StructureKind.AUTHOR in kinds
    assert StructureKind.ABSTRACT in kinds
    assert StructureKind.KEYWORDS in kinds
    assert StructureKind.SECTION in kinds
    assert StructureKind.SUBSECTION in kinds
    assert StructureKind.BIBLIOGRAPHY in kinds
    assert StructureKind.BIBLIOGRAPHY_ENTRY in kinds
    assert StructureKind.APPENDIX in kinds

    nodes = {node.kind: node for node in result.nodes}
    introduction = next(
        node for node in result.nodes if node.title == "Introduction"
    )
    context = next(node for node in result.nodes if node.title == "Context")
    bibliography = nodes[StructureKind.BIBLIOGRAPHY]
    entry = nodes[StructureKind.BIBLIOGRAPHY_ENTRY]

    assert introduction.evidence_type == "text_and_table_of_contents"
    assert introduction.heading_level == 1
    assert introduction.heading_confidence == 0.98
    assert context.parent_id == introduction.node_id
    assert context.node_id in introduction.child_ids
    assert entry.parent_id == bibliography.node_id
    assert entry.evidence_status is StructureEvidenceStatus.OBSERVED
    assert entry.node_id in bibliography.child_ids
    assert all(node.source_spans for node in result.nodes)
    assert result.analysis_id is not None
    assert result.layout_result_ids
    assert result.input_block_ids
    assert all(
        set(node.source_block_ids).issubset(result.input_block_ids)
        for node in result.nodes
    )

    ordered = [node for node in result.nodes if node.reading_order is not None]
    assert {node.reading_order for node in ordered} == set(range(len(ordered)))
    assert all(node.reading_order_confidence is not None for node in ordered)


def test__article_structure__groups_abstract_body_without_replacing_text() -> (
    None
):
    document = _document(
        (
            "A Deterministic Article",
            "Abstract",
            "First abstract paragraph.",
            "Second abstract paragraph.",
            "1 Introduction",
        )
    )

    result = _analyze(document)
    abstract = next(
        node for node in result.nodes if node.kind is StructureKind.ABSTRACT
    )

    assert len(abstract.source_block_ids) == 3
    assert len(abstract.source_spans) == 3
    assert abstract.title == "Abstract"


def test__article_structure__marks_fallback_title_as_uncertain() -> None:
    document = _document(
        ("Proposed title", "1 Introduction"),
        metadata_title=None,
    )

    result = _analyze(document)
    title = next(
        node for node in result.nodes if node.kind is StructureKind.TITLE
    )

    assert title.confidence == 0.45
    assert title.warning_ids
    assert any(
        warning.code == "structure.fallback_title"
        for warning in result.warnings
    )


def test__article_structure__represents_empty_text_evidence() -> None:
    document = _document((), metadata_title=None)

    result = _analyze(document)

    assert not result.nodes
    assert any(
        warning.code == "structure.no_text_evidence"
        for warning in result.warnings
    )


def test__article_structure__rejects_stale_layout_evidence() -> None:
    document = _document(("A Deterministic Article",))
    other = _document(
        ("A Deterministic Article",), source_bytes=b"other article bytes"
    )
    stale_layouts = DeterministicLayoutProcessor().analyze(other)

    with pytest.raises(ValueError, match="does not match"):
        DeterministicArticleStructureAnalyzer().analyze_with_layout(
            document, stale_layouts
        )


def test__article_structure__enforces_pre_analysis_bounds() -> None:
    document = _document(("First", "Second"), metadata_title=None)
    analyzer = DeterministicArticleStructureAnalyzer(
        ArticleStructureConfiguration(max_text_blocks=1)
    )

    with pytest.raises(ArticleStructureLimitError, match="text blocks"):
        analyzer.analyze(document)


def test__article_structure__is_deterministic_and_immutable() -> None:
    document = _document(("A Deterministic Article", "1 Introduction", "Body"))

    first = _analyze(document)
    second = _analyze(document)

    assert first == second
    assert first.analysis_id == second.analysis_id
    with pytest.raises(FrozenInstanceError):
        first.analysis_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="inconsistent"):
        replace(first, analysis_id="changed")
    with pytest.raises(ValueError, match="inconsistent"):
        replace(first.nodes[0], node_id="changed")
    ordered_node = next(
        node for node in first.nodes if node.reading_order is not None
    )
    assert ordered_node.reading_order is not None
    shifted = replace(
        ordered_node,
        reading_order=ordered_node.reading_order + 1,
    )
    assert shifted.node_id == ordered_node.node_id


def test__article_structure__analyzes_pdf_fixture_matrix() -> None:
    pytest.importorskip("fitz")
    fixture_root = Path(__file__).parent / "fixtures" / "pdf"
    analyzer = DeterministicArticleStructureAnalyzer()
    extractor = PyMuPdfExtractor()

    for path in sorted(fixture_root.glob("*.pdf")):
        payload = path.read_bytes()
        source = SourceDocument.from_bytes(
            payload,
            source_id=f"fixture:{path.stem}",
            media_type="application/pdf",
            locator=str(path),
        )
        document = extractor.extract(source, BytesIO(payload)).document
        result = analyzer.analyze(document)

        assert result.analysis_id is not None
        assert result.source_id == source.source_id
        assert result.source_blob_id == source.blob_id
        assert result.layout_result_ids == tuple(
            layout.result_id
            for layout in analyzer.layout_processor.analyze(document)
        )


def test__article_structure__bibliography_entries_cannot_claim_acceptance() -> (
    None
):
    document = _document(
        (
            "A Deterministic Article",
            "References",
            "[1] A. Author. An observed reference.",
        )
    )
    result = _analyze(document)
    entry = next(
        node
        for node in result.nodes
        if node.kind is StructureKind.BIBLIOGRAPHY_ENTRY
    )

    with pytest.raises(ValueError, match="observations"):
        replace(entry, evidence_status=StructureEvidenceStatus.PROPOSED)
