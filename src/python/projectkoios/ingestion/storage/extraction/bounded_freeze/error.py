"""Typed I/O failure for bounded extraction freezing."""

from __future__ import annotations

from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)


class BoundedExtractionFreezeError(RuntimeError):
    """Port failure with an explicit authority/retry/stop disposition."""

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
            raise ValueError("bounded extraction failure must be complete")
        if not isinstance(disposition, ExtractionActionDisposition):
            raise TypeError("bounded extraction disposition is invalid")
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("bounded extraction failure cannot continue")
        super().__init__(message)
        self.code = code
        self.disposition = disposition
