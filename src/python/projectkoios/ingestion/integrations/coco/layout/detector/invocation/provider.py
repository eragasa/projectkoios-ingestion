"""Provider port for bounded verified local detector execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from projectkoios.ingestion.integrations.coco.layout.detector.invocation.request import (  # noqa: E501
    CocoLayoutDetectorInvocationRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.result import (  # noqa: E501
    CocoLayoutDetectorInvocationFailureKind,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(slots=True)
class CocoLayoutDetectorProviderError(Exception):
    """Expose one bounded provider failure without vendor exception leakage."""

    kind: CocoLayoutDetectorInvocationFailureKind
    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CocoLayoutDetectorInvocationFailureKind):
            raise TypeError("kind must be a detector invocation failure kind")
        LayoutValueValidation.require_text("code", self.code)
        Exception.__init__(self, self.code)


class CocoLayoutDetectorInvocationProvider(ABC):
    """Verify exact bytes and execute one immutable detector request."""

    @property
    @abstractmethod
    def implementation_id(self) -> str:
        """Return the exact provider implementation and version identity."""

    @abstractmethod
    def invoke(self, *, request: CocoLayoutDetectorInvocationRequest) -> bytes:
        """Return exact bounded raw output or raise one typed failure."""
