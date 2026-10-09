"""Strict local detector raw-output parsing requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.identity import stable_id

from ..result import CocoLayoutDetectorInvocationResult


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorOutputParsingRequest(DataObjectActionRequest):
    """Bind parsing to one exact completed or failed invocation."""

    invocation: CocoLayoutDetectorInvocationResult
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.invocation) is not CocoLayoutDetectorInvocationResult:
            raise TypeError(
                "invocation must be CocoLayoutDetectorInvocationResult"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "coco-layout-detector-output-parsing-request",
                self.invocation.invocation_id,
            ),
        )
