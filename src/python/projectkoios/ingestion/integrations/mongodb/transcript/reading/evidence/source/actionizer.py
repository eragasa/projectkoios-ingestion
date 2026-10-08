"""MongoDB front-end action for canonical reading-evidence sourcing."""

from __future__ import annotations

from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.source.reader import (  # noqa: E501
    MongoReadingEvidenceReadModelReader,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.source.verifier import (  # noqa: E501
    ReadingEvidenceReadModelVerifier,
)
from projectkoios.ingestion.transcript.reading.evidence.source.actionizer import (  # noqa: E501
    ReadingEvidenceSourceActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)


class MongoReadingEvidenceSourceActionizer(ReadingEvidenceSourceActionizer):
    """Compose bounded MongoDB reading with neutral strict verification."""

    __slots__ = ("reader", "verifier")

    def __init__(
        self,
        *,
        reader: MongoReadingEvidenceReadModelReader,
        verifier: ReadingEvidenceReadModelVerifier,
    ) -> None:
        if type(reader) is not MongoReadingEvidenceReadModelReader:
            raise TypeError("reader has an unsupported type")
        if type(verifier) is not ReadingEvidenceReadModelVerifier:
            raise TypeError("verifier has an unsupported type")
        self.reader = reader
        self.verifier = verifier

    def action(
        self, *, request: ReadingEvidenceSourceRequest
    ) -> ReadingEvidenceSourceResult:
        """Read one completed generation and return canonical domain values."""
        if type(request) is not ReadingEvidenceSourceRequest:
            raise TypeError("request has an unsupported type")
        read_model = self.reader.read(request=request)
        return self.verifier.verify(
            request=request,
            read_model=read_model,
            provider_implementation_id=self.reader.implementation_id,
        )
