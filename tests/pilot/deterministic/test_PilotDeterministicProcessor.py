from __future__ import annotations

import pytest
from projectkoios.ingestion.bibtex import BibTexRecord
from projectkoios.ingestion.documents.pdf.models import PdfProcessedDocument
from projectkoios.ingestion.pilot import (
    PilotDeterministicProcessor,
    PilotDocument,
)


def test__PilotDeterministicProcessor__requires_retained_extraction() -> None:
    document = PdfProcessedDocument(
        source=PilotDocument(
            source_id=BibTexRecord("pilot-source", "misc", ()),
            locator="pilot.pdf",
            media_type="application/pdf",
            content=b"%PDF",
        ),
        pages=(),
    )

    with pytest.raises(ValueError, match="retained extraction evidence"):
        PilotDeterministicProcessor().process(document)
