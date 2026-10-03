"""Backend-neutral durable processing-state store boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod

from projectkoios.ingestion.storage.processing_state.contracts import (
    ProcessingStateInitializationRequest,
    ProcessingStateLoadRequest,
    ProcessingStateSaveRequest,
    ProcessingStateSaveResult,
    ProcessingStateSnapshot,
)


class AbstractProcessingStateStore(ABC):
    """Initialize, load, and atomically transition bounded checkpoints."""

    __slots__ = ()

    @abstractmethod
    def initialize(
        self, *, request: ProcessingStateInitializationRequest
    ) -> ProcessingStateSnapshot:
        """Create missing queue rows and validate the exact registration."""

    @abstractmethod
    def load(
        self, *, request: ProcessingStateLoadRequest
    ) -> ProcessingStateSnapshot:
        """Load one exact immutable processing checkpoint."""

    @abstractmethod
    def save(
        self, *, request: ProcessingStateSaveRequest
    ) -> ProcessingStateSaveResult:
        """Optimistically commit or exactly replay one state transition."""
