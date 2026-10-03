from __future__ import annotations

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.storage.extraction.publication.result import (
    ExtractionPublicationResult,
)


def test__extraction_publication_result__retains_commit_position() -> None:
    result = ExtractionPublicationResult(
        request_id="request:one",
        document_id="document:one",
        payload_sha256="a" * 64,
        payload_byte_size=10,
        journal_sequence=1,
        replayed=False,
    )

    assert isinstance(result, DataObjectActionResult)
    assert result.journal_sequence == 1
    assert result.replayed is False
