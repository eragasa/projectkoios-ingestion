"""Typed extraction projection subset recovery backend failure."""

from __future__ import annotations

from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)


class ExtractionProjectionSubsetRecoveryBackendError(RuntimeError):
    """Recovery failure with explicit authority/retry/stop disposition."""

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
            raise ValueError("subset-recovery failure must be complete")
        if not isinstance(disposition, ExtractionActionDisposition):
            raise TypeError("subset-recovery disposition is invalid")
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("subset-recovery failure cannot continue")
        super().__init__(message)
        self.code = code
        self.disposition = disposition
