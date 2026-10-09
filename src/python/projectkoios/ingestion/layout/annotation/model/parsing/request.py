"""Immutable request for strict model-response parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.model.invocation import (
    LayoutAnnotationModelInvocationResult,
)


@dataclass(frozen=True, slots=True)
class LayoutModelResponseParsingRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Request strict parsing of one exact raw model response."""

    CONTRACT_NAME: ClassVar[str] = "layout-model-response-parsing-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    invocation: LayoutAnnotationModelInvocationResult
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.invocation) is not LayoutAnnotationModelInvocationResult:
            raise TypeError(
                "invocation must be LayoutAnnotationModelInvocationResult"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.invocation.invocation_id,
            ),
        )
