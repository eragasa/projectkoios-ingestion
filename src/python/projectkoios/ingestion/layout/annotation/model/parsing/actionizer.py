"""Strict bounded parser operation for model-authored annotations."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.layout.annotation.model.parsing.derivation import (
    LayoutModelResponseInterpreter,
)
from projectkoios.ingestion.layout.annotation.model.parsing.request import (
    LayoutModelResponseParsingRequest,
)
from projectkoios.ingestion.layout.annotation.model.parsing.result import (
    LayoutModelResponseParsingResult,
)


class LayoutModelResponseParser(
    DataObjectActionizer[
        LayoutModelResponseParsingRequest,
        LayoutModelResponseParsingResult,
    ]
):
    """Parse exact raw output into validated non-authoritative evidence."""

    def action(
        self, *, request: LayoutModelResponseParsingRequest
    ) -> LayoutModelResponseParsingResult:
        """Return the only valid parsing evidence for the exact invocation."""
        interpretation = LayoutModelResponseInterpreter.interpret(request)
        return LayoutModelResponseParsingResult(
            request=request,
            status=interpretation.status,
            candidate=interpretation.candidate,
            limitation=interpretation.limitation,
        )
