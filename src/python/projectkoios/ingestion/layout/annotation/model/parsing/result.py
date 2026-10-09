"""Typed outcome of strict model-response parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.model.candidate import (
    LayoutModelAnnotationCandidate,
)
from projectkoios.ingestion.layout.annotation.model.limitation import (
    LayoutModelAnnotationLimitation,
)
from projectkoios.ingestion.layout.annotation.model.parsing.derivation import (
    LayoutModelResponseInterpreter,
)
from projectkoios.ingestion.layout.annotation.model.parsing.request import (
    LayoutModelResponseParsingRequest,
)
from projectkoios.ingestion.layout.annotation.model.parsing.status import (
    LayoutModelResponseParsingStatus,
)


@dataclass(frozen=True, slots=True)
class LayoutModelResponseParsingResult(AbstractDataObjectActionResult):
    """Bind a candidate or explicit limitation to one exact invocation."""

    CONTRACT_NAME: ClassVar[str] = "layout-model-response-parsing-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    ACTIONIZER_NAME: ClassVar[str] = "layout-model-response-parser"
    ACTIONIZER_VERSION: ClassVar[str] = "1.0"

    request: LayoutModelResponseParsingRequest
    status: LayoutModelResponseParsingStatus
    candidate: LayoutModelAnnotationCandidate | None
    limitation: LayoutModelAnnotationLimitation | None
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not LayoutModelResponseParsingRequest:
            raise TypeError("request must be LayoutModelResponseParsingRequest")
        if not isinstance(self.status, LayoutModelResponseParsingStatus):
            raise TypeError("status must be LayoutModelResponseParsingStatus")
        interpretation = LayoutModelResponseInterpreter.interpret(self.request)
        if (
            self.status is not interpretation.status
            or self.candidate != interpretation.candidate
            or self.limitation != interpretation.limitation
        ):
            raise ValueError(
                "parsing result differs from exact raw response interpretation"
            )
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.request.request_id,
                self.status,
                None if self.candidate is None else self.candidate.candidate_id,
                None
                if self.limitation is None
                else self.limitation.limitation_id,
                self.ACTIONIZER_NAME,
                self.ACTIONIZER_VERSION,
            ),
        )

    @property
    def invocation_id(self) -> str:
        """Return the exact invocation parsed by this result."""
        return self.request.invocation.invocation_id

    @property
    def replica_index(self) -> int:
        """Return the request-bound replica index."""
        return self.request.invocation.request.replica_index
