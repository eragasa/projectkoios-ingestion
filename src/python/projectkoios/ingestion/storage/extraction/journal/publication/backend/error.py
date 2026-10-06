"""Typed authoritative extraction journal publication failure."""

from __future__ import annotations

from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)


class ValidatedExtractionJournalPublicationBackendError(RuntimeError):
    """Publication failure with an explicit authority/retry/stop disposition."""

    def __init__(
        self,
        *,
        code: str,
        disposition: ExtractionActionDisposition,
        message: str,
    ) -> None:
        if (
            type(code) is not str
            or not code
            or len(code) > 256
            or type(message) is not str
            or not message
        ):
            raise ValueError("journal-publication failure must be complete")
        if not isinstance(disposition, ExtractionActionDisposition):
            raise TypeError("journal-publication disposition is invalid")
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("journal-publication failure cannot continue")
        super().__init__(message)
        self.code = code
        self.disposition = disposition
