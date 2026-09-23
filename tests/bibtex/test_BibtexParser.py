from __future__ import annotations

from pathlib import Path

import pytest
from projectkoios.ingestion.bibtex import (
    BibtexParser,
    BibtexReferenceError,
)

_RESOURCE = (
    Path(__file__).parents[1] / "resources" / "pilot" / "pilot-document.bib"
)


def test__BibtexParser__parse__returns_requested_record() -> None:
    record = BibtexParser().parse(
        _RESOURCE.read_text(encoding="utf-8"),
        "PilotDocument2026",
    )

    assert record.citation_key == "PilotDocument2026"
    assert record.entry_type == "misc"
    assert dict(record.fields)["title"] == "Pilot Ingestion Test Document"


def test__BibtexParser__parse__rejects_missing_record() -> None:
    with pytest.raises(BibtexReferenceError, match="BibTeX record not found"):
        BibtexParser().parse(
            _RESOURCE.read_text(encoding="utf-8"),
            "MissingRecord",
        )
