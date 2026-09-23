from __future__ import annotations

from pathlib import Path

import pytest
from projectkoios.ingestion.base import BaseDocument
from projectkoios.ingestion.bibtex import BibtexParser
from projectkoios.ingestion.documents.pdf import (
    PdfDocumentProcessor,
    ProcessedPdfDocumentDeserializationError,
    ProcessedPdfDocumentDeserializer,
)
from projectkoios.ingestion.pdf import PyMuPdfExtractor
from projectkoios.ingestion.serialization import serialize_contract

pytest.importorskip("pymupdf")
_RESOURCES = Path(__file__).parents[2] / "resources" / "pilot"


def _write_processed_document(root: Path) -> tuple[Path, Path, Path]:
    bibtex = root / "pilot-document.bib"
    pdf = root / "pilot-document.pdf"
    artifact = root / "extraction.json"
    bibtex.write_bytes((_RESOURCES / "pilot-document.bib").read_bytes())
    pdf.write_bytes((_RESOURCES / "pilot-document.pdf").read_bytes())
    record = BibtexParser().parse(
        bibtex.read_text(encoding="utf-8"), "PilotDocument2026"
    )
    processed = PdfDocumentProcessor(
        PyMuPdfExtractor(low_text_character_threshold=0)
    ).process(
        BaseDocument(
            source_id=record,
            locator="corpus/pilot-document.pdf",
            media_type="application/pdf",
            content=pdf.read_bytes(),
        )
    )
    assert processed.extraction is not None
    artifact.write_text(
        serialize_contract(processed.extraction) + "\n", encoding="utf-8"
    )
    return bibtex, pdf, artifact


def test__ProcessedPdfDocumentDeserializer__deserialize__loads_verified_sources(
    tmp_path: Path,
) -> None:
    bibtex, pdf, artifact = _write_processed_document(tmp_path)

    document = ProcessedPdfDocumentDeserializer().deserialize(
        citation_key="PilotDocument2026",
        bibtex_path=bibtex,
        pdf_path=pdf,
        processed_document_path=artifact,
    )

    assert document.source.source_id.citation_key == "PilotDocument2026"
    assert document.source.content == pdf.read_bytes()
    assert document.source.locator == "corpus/pilot-document.pdf"
    assert document.extraction is not None
    assert document.extraction.document.source.content_hash == (
        document.extraction.manifest.source_content_hash
    )
    assert [page.text for page in document.pages] == [
        "Alpha evidence",
        "Beta retrieval evidence",
    ]


def test__ProcessedPdfDocumentDeserializer__deserialize__rejects_stale_pdf(
    tmp_path: Path,
) -> None:
    bibtex, pdf, artifact = _write_processed_document(tmp_path)
    pdf.write_bytes(pdf.read_bytes() + b"stale")

    with pytest.raises(
        ProcessedPdfDocumentDeserializationError,
        match="does not match the exact PDF source",
    ):
        ProcessedPdfDocumentDeserializer().deserialize(
            citation_key="PilotDocument2026",
            bibtex_path=bibtex,
            pdf_path=pdf,
            processed_document_path=artifact,
        )


def test__ProcessedPdfDocumentDeserializer__rejects_malformed_artifact(
    tmp_path: Path,
) -> None:
    bibtex, pdf, artifact = _write_processed_document(tmp_path)
    artifact.write_text('{"document":', encoding="utf-8")

    with pytest.raises(
        ProcessedPdfDocumentDeserializationError,
        match="invalid extraction artifact",
    ):
        ProcessedPdfDocumentDeserializer().deserialize(
            citation_key="PilotDocument2026",
            bibtex_path=bibtex,
            pdf_path=pdf,
            processed_document_path=artifact,
        )
