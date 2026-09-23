from __future__ import annotations

from projectkoios.ingestion.base import (
    BaseDeterministicProcessor,
    BaseProcessedDocument,
)


class DeterministicProcessor(BaseDeterministicProcessor):
    """Stub composition root for an ordered deterministic component prefix."""

    name = "deterministic-processor"
    version = "0"

    def process(
        self,
        document: BaseProcessedDocument,
    ) -> BaseProcessedDocument:
        raise NotImplementedError(
            "deterministic component composition is not implemented"
        )


__all__ = ["DeterministicProcessor"]
