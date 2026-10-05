"""Typed extraction projection index-readiness backend failure."""

from __future__ import annotations

from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)


class ExtractionProjectionIndexReadinessBackendError(RuntimeError):
    """Report one readiness failure with an explicit workflow disposition."""

    def __init__(
        self,
        *,
        code: str,
        disposition: ExtractionActionDisposition,
        message: str,
    ) -> None:
        if type(code) is not str or not code or len(code) > 256:
            raise ValueError("index-readiness error code is invalid")
        if type(message) is not str or not message:
            raise ValueError("index-readiness error message is invalid")
        if not isinstance(disposition, ExtractionActionDisposition):
            raise TypeError("index-readiness disposition is invalid")
        if disposition is ExtractionActionDisposition.CONTINUE:
            raise ValueError("index-readiness failure cannot continue")
        super().__init__(message)
        self.code = code
        self.disposition = disposition
