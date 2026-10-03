from __future__ import annotations

from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)


def test__extraction_publication_record__chains_exact_payload() -> None:
    record = ExtractionPublicationRecord.create(
        sequence=2,
        request_id="request:two",
        document_id="document:two",
        manifest_id="manifest:two",
        payload_sha256="a" * 64,
        payload_byte_size=42,
        previous_record_sha256="b" * 64,
    )

    assert record.sequence == 2
    assert record.previous_record_sha256 == "b" * 64
    assert len(record.record_sha256) == 64
