"""Runtime-neutral model invocation operation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.layout.annotation.model.invocation import (
    LayoutAnnotationModelInvocationResult,
)
from projectkoios.ingestion.layout.annotation.model.request import (
    LayoutAnnotationModelRequest,
)


class LayoutAnnotationModelActionizer(
    DataObjectActionizer[
        LayoutAnnotationModelRequest,
        LayoutAnnotationModelInvocationResult,
    ],
    ABC,
):
    """Invoke one bound model without owning retries or approvals."""

    @abstractmethod
    def action(
        self, *, request: LayoutAnnotationModelRequest
    ) -> LayoutAnnotationModelInvocationResult:
        """Execute one request and retain exact invocation evidence."""
