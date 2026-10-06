"""Typed artifact-reader failure visible to Workflow."""

from __future__ import annotations

from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)


class ExtractionArtifactReaderError(RuntimeError):
    """Reader failure with an explicit retry/stop disposition."""

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
            raise ValueError("artifact reader failure must be complete")
        if not isinstance(disposition, ExtractionActionDisposition):
            raise TypeError("artifact reader failure disposition is invalid")
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("artifact reader failure cannot continue")
        super().__init__(message)
        self.code = code
        self.disposition = disposition
