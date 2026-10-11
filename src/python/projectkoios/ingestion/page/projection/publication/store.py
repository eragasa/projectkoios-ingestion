"""Owner-neutral durable journal capability for publication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager

from projectkoios.ingestion.page.projection.publication.receipt import (
    PageProjectionPublicationReceipt,
)
from projectkoios.ingestion.page.projection.publication.request import (
    PageProjectionPublicationRequest,
)
from projectkoios.ingestion.page.projection.publication.result import (
    PageProjectionPublicationResult,
)


class PageProjectionPublicationJournal(ABC):
    """Own current reads, replay, head CAS, and commit under one lock."""

    __slots__ = ()

    @abstractmethod
    def read_current(self) -> PageProjectionPublicationReceipt | None:
        """Return the integrity-verified current safe receipt, when present."""
        raise NotImplementedError

    @abstractmethod
    def replay(
        self, *, request: PageProjectionPublicationRequest
    ) -> PageProjectionPublicationResult | None:
        """Return an exact durable replay before evaluating current head."""
        raise NotImplementedError

    @abstractmethod
    def require_current(
        self, *, request: PageProjectionPublicationRequest
    ) -> None:
        """Require the exact caller-declared current publication head."""
        raise NotImplementedError

    @abstractmethod
    def commit(
        self,
        *,
        request: PageProjectionPublicationRequest,
        receipt: PageProjectionPublicationReceipt,
        payload: bytes,
    ) -> PageProjectionPublicationResult:
        """Commit objects and state, then reread the authoritative result."""
        raise NotImplementedError


class PageProjectionPublicationStore(ABC):
    """Provide a trusted durable publication scope and subject journals."""

    __slots__ = ()

    @property
    @abstractmethod
    def implementation_id(self) -> str:
        """Return the exact store implementation identity."""
        raise NotImplementedError

    @property
    @abstractmethod
    def scope_id(self) -> str:
        """Return the immutable trusted deployment/publication scope."""
        raise NotImplementedError

    @abstractmethod
    def read_current(
        self, *, source_artifact_id: str
    ) -> PageProjectionPublicationReceipt | None:
        """Read one current receipt under the source-subject lock."""
        raise NotImplementedError

    @abstractmethod
    def open_journal(
        self, *, source_artifact_id: str
    ) -> AbstractContextManager[PageProjectionPublicationJournal]:
        """Lock and open one content-addressed source subject journal."""
        raise NotImplementedError
