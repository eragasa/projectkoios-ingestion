from __future__ import annotations

from pathlib import Path

from projectkoios.ingestion.base import BaseDocument
from projectkoios.ingestion.bibtex import BibtexParser
from projectkoios.ingestion.pilot import PilotDocument

_RESOURCES = Path(__file__).parents[2] / "resources" / "pilot"


def test__PilotDocument__construction__creates_concrete_base_document() -> None:
    record = BibtexParser().parse(
        (_RESOURCES / "pilot-document.bib").read_text(encoding="utf-8"),
        "PilotDocument2026",
    )
    document = PilotDocument(
        source_id=record,
        locator="pilot-document.pdf",
        media_type="application/pdf",
        content=(_RESOURCES / "pilot-document.pdf").read_bytes(),
    )

    assert isinstance(document, BaseDocument)
    assert document.source_id.citation_key == "PilotDocument2026"
