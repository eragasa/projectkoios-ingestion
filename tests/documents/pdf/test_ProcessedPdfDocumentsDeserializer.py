from __future__ import annotations

import json
from pathlib import Path

import pytest
from projectkoios.ingestion.base import BaseDocument
from projectkoios.ingestion.bibtex import BibtexParser
from projectkoios.ingestion.documents.pdf.errors import (
    ProcessedPdfDocumentDeserializationError,
)
from projectkoios.ingestion.documents.pdf.models import (
    PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION,
)
from projectkoios.ingestion.documents.pdf.processed_documents import (
    ProcessedPdfDocumentsDeserializer,
)
from projectkoios.ingestion.documents.pdf.processor import PdfDocumentProcessor
from projectkoios.ingestion.pdf import PyMuPdfExtractor
from projectkoios.ingestion.serialization import serialize_contract

pytest.importorskip("pymupdf")
_RESOURCES = Path(__file__).parents[2] / "resources" / "pilot"


def _prepare_corpus(root: Path) -> Path:
    sources = root / "sources"
    processed_root = root / "processed"
    sources.mkdir()
    processed_root.mkdir()
    original_bibtex = (_RESOURCES / "pilot-document.bib").read_text(
        encoding="utf-8"
    )
    second_bibtex = original_bibtex.replace(
        "PilotDocument2026", "SecondDocument2026"
    )
    bibtex = sources / "corpus.bibtex"
    bibtex.write_text(original_bibtex + "\n" + second_bibtex, encoding="utf-8")
    payload = (_RESOURCES / "pilot-document.pdf").read_bytes()
    items: list[dict[str, str]] = []
    for citation_key, stem in (
        ("PilotDocument2026", "first"),
        ("SecondDocument2026", "second"),
    ):
        pdf = sources / f"{stem}.pdf"
        pdf.write_bytes(payload)
        record = BibtexParser().parse(
            bibtex.read_text(encoding="utf-8"), citation_key
        )
        document = PdfDocumentProcessor(
            PyMuPdfExtractor(low_text_character_threshold=0)
        ).process(
            BaseDocument(
                source_id=record,
                locator=f"sources/{stem}.pdf",
                media_type="application/pdf",
                content=payload,
            )
        )
        assert document.extraction is not None
        artifact = processed_root / f"{stem}.json"
        artifact.write_text(
            serialize_contract(document.extraction) + "\n",
            encoding="utf-8",
        )
        items.append(
            {
                "citation_key": citation_key,
                "bibtex_path": "sources/corpus.bibtex",
                "pdf_path": f"sources/{stem}.pdf",
                "processed_document_path": f"processed/{stem}.json",
            }
        )
    manifest = root / "corpus.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": PROCESSED_PDF_DOCUMENTS_SCHEMA_VERSION,
                "items": items,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test__ProcessedPdfDocumentsDeserializer__preserves_manifest_order(
    tmp_path: Path,
) -> None:
    manifest = _prepare_corpus(tmp_path)

    corpus = ProcessedPdfDocumentsDeserializer().deserialize(manifest)

    assert [
        document.source.source_id.citation_key for document in corpus.documents
    ] == ["PilotDocument2026", "SecondDocument2026"]
    assert all(document.extraction is not None for document in corpus.documents)


def test__ProcessedPdfDocumentsDeserializer__rejects_unsafe_location(
    tmp_path: Path,
) -> None:
    manifest = _prepare_corpus(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["items"][0]["pdf_path"] = "../outside.pdf"
    manifest.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(
        ProcessedPdfDocumentDeserializationError,
        match="safe relative path",
    ):
        ProcessedPdfDocumentsDeserializer().deserialize(manifest)


def test__ProcessedPdfDocumentsDeserializer__rejects_duplicate_sources(
    tmp_path: Path,
) -> None:
    manifest = _prepare_corpus(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["items"][1]["citation_key"] = value["items"][0]["citation_key"]
    manifest.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(
        ProcessedPdfDocumentDeserializationError,
        match="duplicate citation_key",
    ):
        ProcessedPdfDocumentsDeserializer().deserialize(manifest)
