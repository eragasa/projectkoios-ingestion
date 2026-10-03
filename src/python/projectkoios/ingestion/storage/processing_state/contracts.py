"""Backend-neutral immutable contracts for bounded processing state."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest, DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

_MAX_BOOKS = 512
_MAX_CHUNKS = 100_000
_MAX_PAGES_PER_BOOK = 1_000_000
_MAX_CHUNK_PAGES = 10_000
_MAX_CANDIDATES = 1_000_000
_MAX_EVENTS_PER_SAVE = 1_024
_MAX_NAME_CHARACTERS = 512
_MAX_LABEL_CHARACTERS = 4_096
_MAX_ERROR_CHARACTERS = 65_536
_MAX_ARTIFACT_PATH_CHARACTERS = 4_096


class ProcessingStateSaveStatus(StrEnum):
    """Whether a state transition was newly committed or exactly replayed."""

    COMMITTED = "committed"
    UNCHANGED = "unchanged"


def _bounded_string(
    name: str,
    value: str,
    *,
    maximum: int = _MAX_NAME_CHARACTERS,
    allow_empty: bool = False,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if (
        (not allow_empty and not value)
        or len(value) > maximum
        or "\x00" in value
    ):
        raise ValueError(f"{name} is invalid")


def _positive_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


def _finite_nonnegative(name: str, value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric or None")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")


def _optional_error(value: str | None) -> None:
    if value is not None:
        _bounded_string(
            "error", value, maximum=_MAX_ERROR_CHARACTERS, allow_empty=False
        )


@dataclass(frozen=True, slots=True)
class ProcessingBookRegistration(AbstractImmutableDataObject):
    """Immutable queue geometry for one processing book."""

    CONTRACT_NAME: ClassVar[str] = "processing-book-registration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    name: str
    queue_order: int
    pages: int
    chunk_pages: int

    def __post_init__(self) -> None:
        _bounded_string("book name", self.name)
        for name, value in (
            ("queue_order", self.queue_order),
            ("pages", self.pages),
            ("chunk_pages", self.chunk_pages),
        ):
            _positive_integer(name, value)
        if self.pages > _MAX_PAGES_PER_BOOK:
            raise ValueError("book pages exceed the bound")
        if self.chunk_pages > _MAX_CHUNK_PAGES:
            raise ValueError("chunk_pages exceeds the bound")
        if self.chunks > _MAX_CHUNKS:
            raise ValueError("book chunk count exceeds the bound")

    @property
    def chunks(self) -> int:
        return math.ceil(self.pages / self.chunk_pages)


@dataclass(frozen=True, slots=True)
class ProcessingBookState(AbstractImmutableDataObject):
    """Mutable workflow checkpoint values for one registered book."""

    CONTRACT_NAME: ClassVar[str] = "processing-book-state"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    name: str
    queue_order: int
    pages: int
    chunks: int
    stage: str
    state: str
    equation_candidates: int
    figure_candidates: int
    primary_equations: int
    paragraphs: int
    runtime_seconds: float
    error: str | None
    updated: float

    def __post_init__(self) -> None:
        _bounded_string("book name", self.name)
        _bounded_string("book stage", self.stage)
        _bounded_string("book state", self.state)
        for name, value in (
            ("queue_order", self.queue_order),
            ("pages", self.pages),
            ("chunks", self.chunks),
        ):
            _positive_integer(name, value)
        if self.pages > _MAX_PAGES_PER_BOOK or self.chunks > _MAX_CHUNKS:
            raise ValueError("book state geometry exceeds the bound")
        for name, value in (
            ("equation_candidates", self.equation_candidates),
            ("figure_candidates", self.figure_candidates),
            ("primary_equations", self.primary_equations),
            ("paragraphs", self.paragraphs),
        ):
            _nonnegative_integer(name, value)
        _finite_nonnegative("runtime_seconds", self.runtime_seconds)
        _finite_nonnegative("updated", self.updated)
        _optional_error(self.error)


@dataclass(frozen=True, slots=True)
class ProcessingChunkState(AbstractImmutableDataObject):
    """Checkpoint state for one contiguous physical-page chunk."""

    CONTRACT_NAME: ClassVar[str] = "processing-chunk-state"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    book: str
    chunk_number: int
    first_page: int
    last_page: int
    detection_state: str
    equation_state: str
    equation_count: int
    figure_count: int
    detection_seconds: float | None
    equation_seconds: float | None
    error: str | None
    updated: float

    def __post_init__(self) -> None:
        _bounded_string("chunk book", self.book)
        _bounded_string("detection state", self.detection_state)
        _bounded_string("equation state", self.equation_state)
        for name, value in (
            ("chunk_number", self.chunk_number),
            ("first_page", self.first_page),
            ("last_page", self.last_page),
        ):
            _positive_integer(name, value)
        if self.last_page < self.first_page:
            raise ValueError("chunk page range must be ordered")
        _nonnegative_integer("equation_count", self.equation_count)
        _nonnegative_integer("figure_count", self.figure_count)
        _finite_nonnegative("detection_seconds", self.detection_seconds)
        _finite_nonnegative("equation_seconds", self.equation_seconds)
        _finite_nonnegative("updated", self.updated)
        _optional_error(self.error)


@dataclass(frozen=True, slots=True)
class ProcessingCandidateState(AbstractImmutableDataObject):
    """Checkpoint state and artifact locator for one detected candidate."""

    CONTRACT_NAME: ClassVar[str] = "processing-candidate-state"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    book: str
    kind: str
    chunk_number: int
    ordinal: int
    label: str
    source_page: int
    owner_id: str
    state: str
    runtime_seconds: float | None
    error: str | None
    artifact_path: str
    updated: float

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("candidate book", self.book, _MAX_NAME_CHARACTERS),
            ("candidate kind", self.kind, _MAX_NAME_CHARACTERS),
            ("candidate label", self.label, _MAX_LABEL_CHARACTERS),
            ("candidate owner ID", self.owner_id, _MAX_LABEL_CHARACTERS),
            ("candidate state", self.state, _MAX_NAME_CHARACTERS),
            (
                "candidate artifact path",
                self.artifact_path,
                _MAX_ARTIFACT_PATH_CHARACTERS,
            ),
        ):
            _bounded_string(name, value, maximum=maximum)
        if self.kind not in {"equation", "figure"}:
            raise ValueError("candidate kind is unsupported")
        _positive_integer("chunk_number", self.chunk_number)
        _positive_integer("ordinal", self.ordinal)
        _positive_integer("source_page", self.source_page)
        if (
            self.artifact_path.startswith(("/", "\\"))
            or "\\" in self.artifact_path
            or ".." in self.artifact_path.split("/")
        ):
            raise ValueError(
                "candidate artifact path must be relative and contained"
            )
        _finite_nonnegative("runtime_seconds", self.runtime_seconds)
        _finite_nonnegative("updated", self.updated)
        _optional_error(self.error)

    @property
    def key(self) -> tuple[str, str, int, int]:
        return (self.book, self.kind, self.chunk_number, self.ordinal)


@dataclass(frozen=True, slots=True)
class ProcessingEventDraft(AbstractImmutableDataObject):
    """Idempotent event to append with one state transition."""

    CONTRACT_NAME: ClassVar[str] = "processing-event-draft"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    event_id: str
    created: float
    book: str
    label: str
    detail: str

    @classmethod
    def create(
        cls,
        *,
        created: float,
        book: str,
        label: str,
        detail: str,
    ) -> ProcessingEventDraft:
        return cls(
            event_id=stable_id(
                "processing-event",
                cls.CONTRACT_VERSION,
                created,
                book,
                label,
                detail,
            ),
            created=created,
            book=book,
            label=label,
            detail=detail,
        )

    def __post_init__(self) -> None:
        _finite_nonnegative("event created", self.created)
        _bounded_string("event book", self.book)
        _bounded_string(
            "event label", self.label, maximum=_MAX_LABEL_CHARACTERS
        )
        _bounded_string(
            "event detail", self.detail, maximum=_MAX_ERROR_CHARACTERS
        )
        expected = stable_id(
            "processing-event",
            self.CONTRACT_VERSION,
            self.created,
            self.book,
            self.label,
            self.detail,
        )
        if self.event_id != expected:
            raise ValueError("processing event ID is inconsistent")


@dataclass(frozen=True, slots=True)
class ProcessingStateSnapshot(AbstractImmutableDataObject):
    """Exact bounded processing checkpoint independent of its backend."""

    CONTRACT_NAME: ClassVar[str] = "processing-state-snapshot"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    snapshot_id: str
    books: tuple[ProcessingBookState, ...]
    chunks: tuple[ProcessingChunkState, ...]
    candidates: tuple[ProcessingCandidateState, ...]

    @classmethod
    def create(
        cls,
        *,
        books: tuple[ProcessingBookState, ...],
        chunks: tuple[ProcessingChunkState, ...],
        candidates: tuple[ProcessingCandidateState, ...],
    ) -> ProcessingStateSnapshot:
        ordered_books = tuple(sorted(books, key=lambda item: item.queue_order))
        ordered_chunks = tuple(
            sorted(chunks, key=lambda item: (item.book, item.chunk_number))
        )
        ordered_candidates = tuple(
            sorted(candidates, key=lambda item: item.key)
        )
        cls._validate_values(ordered_books, ordered_chunks, ordered_candidates)
        return cls(
            snapshot_id=stable_id(
                "processing-state-snapshot",
                cls.CONTRACT_VERSION,
                ordered_books,
                ordered_chunks,
                ordered_candidates,
            ),
            books=ordered_books,
            chunks=ordered_chunks,
            candidates=ordered_candidates,
        )

    def __post_init__(self) -> None:
        self._validate_values(self.books, self.chunks, self.candidates)
        if self.books != tuple(
            sorted(self.books, key=lambda item: item.queue_order)
        ):
            raise ValueError("processing books are not canonically ordered")
        if self.chunks != tuple(
            sorted(self.chunks, key=lambda item: (item.book, item.chunk_number))
        ):
            raise ValueError("processing chunks are not canonically ordered")
        if self.candidates != tuple(
            sorted(self.candidates, key=lambda item: item.key)
        ):
            raise ValueError(
                "processing candidates are not canonically ordered"
            )
        expected = stable_id(
            "processing-state-snapshot",
            self.CONTRACT_VERSION,
            self.books,
            self.chunks,
            self.candidates,
        )
        if self.snapshot_id != expected:
            raise ValueError("processing state snapshot ID is inconsistent")

    @staticmethod
    def _validate_values(
        books: tuple[ProcessingBookState, ...],
        chunks: tuple[ProcessingChunkState, ...],
        candidates: tuple[ProcessingCandidateState, ...],
    ) -> None:
        if (
            not isinstance(books, tuple)
            or not isinstance(chunks, tuple)
            or not isinstance(candidates, tuple)
        ):
            raise TypeError(
                "processing state collections must be immutable tuples"
            )
        if not books or len(books) > _MAX_BOOKS:
            raise ValueError("processing state book count is unsupported")
        if len(chunks) > _MAX_CHUNKS or len(candidates) > _MAX_CANDIDATES:
            raise ValueError("processing state exceeds its bounded inventory")
        if any(type(item) is not ProcessingBookState for item in books):
            raise TypeError("books must contain ProcessingBookState values")
        if any(type(item) is not ProcessingChunkState for item in chunks):
            raise TypeError("chunks must contain ProcessingChunkState values")
        if any(
            type(item) is not ProcessingCandidateState for item in candidates
        ):
            raise TypeError(
                "candidates must contain ProcessingCandidateState values"
            )
        book_by_name = {book.name: book for book in books}
        if len(book_by_name) != len(books):
            raise ValueError("processing book names must be unique")
        if len({book.queue_order for book in books}) != len(books):
            raise ValueError("processing queue order must be unique")
        chunk_by_key = {
            (chunk.book, chunk.chunk_number): chunk for chunk in chunks
        }
        if len(chunk_by_key) != len(chunks):
            raise ValueError("processing chunk keys must be unique")
        chunks_by_book: dict[str, list[ProcessingChunkState]] = {}
        for chunk in chunks:
            chunks_by_book.setdefault(chunk.book, []).append(chunk)
        for book in books:
            owned = chunks_by_book.get(book.name, [])
            if len(owned) != book.chunks:
                raise ValueError("processing chunk inventory is incomplete")
            expected_first = 1
            for number, chunk in enumerate(owned, start=1):
                if (
                    chunk.chunk_number != number
                    or chunk.first_page != expected_first
                ):
                    raise ValueError(
                        "processing chunk coverage is not contiguous"
                    )
                expected_first = chunk.last_page + 1
            if expected_first != book.pages + 1:
                raise ValueError(
                    "processing chunk coverage differs from book pages"
                )
        if any(chunk.book not in book_by_name for chunk in chunks):
            raise ValueError("processing chunk refers to an unknown book")
        if len({candidate.key for candidate in candidates}) != len(candidates):
            raise ValueError("processing candidate keys must be unique")
        for candidate in candidates:
            candidate_chunk = chunk_by_key.get(
                (candidate.book, candidate.chunk_number)
            )
            if candidate_chunk is None:
                raise ValueError(
                    "processing candidate refers to an unknown chunk"
                )
            if not (
                candidate_chunk.first_page
                <= candidate.source_page
                <= candidate_chunk.last_page
            ):
                raise ValueError(
                    "processing candidate page is outside its chunk"
                )
        candidate_counts: dict[tuple[str, int, str], int] = {}
        for candidate in candidates:
            key = (candidate.book, candidate.chunk_number, candidate.kind)
            candidate_counts[key] = candidate_counts.get(key, 0) + 1
        for chunk in chunks:
            if chunk.equation_count != candidate_counts.get(
                (chunk.book, chunk.chunk_number, "equation"), 0
            ):
                raise ValueError("chunk equation count differs from candidates")
            if chunk.figure_count != candidate_counts.get(
                (chunk.book, chunk.chunk_number, "figure"), 0
            ):
                raise ValueError("chunk figure count differs from candidates")
        for book in books:
            owned_chunks = chunks_by_book.get(book.name, [])
            if book.equation_candidates != sum(
                chunk.equation_count for chunk in owned_chunks
            ):
                raise ValueError(
                    "book equation candidate count differs from chunks"
                )
            if book.figure_candidates != sum(
                chunk.figure_count for chunk in owned_chunks
            ):
                raise ValueError(
                    "book figure candidate count differs from chunks"
                )


@dataclass(frozen=True, slots=True)
class ProcessingStateInitializationRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Create or validate one exact processing queue registration."""

    CONTRACT_NAME: ClassVar[str] = "processing-state-initialization-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    registrations: tuple[ProcessingBookRegistration, ...]
    created: float

    @classmethod
    def create(
        cls,
        *,
        registrations: tuple[ProcessingBookRegistration, ...],
        created: float,
    ) -> ProcessingStateInitializationRequest:
        return cls(
            request_id=stable_id(
                "processing-state-initialization-request",
                cls.CONTRACT_VERSION,
                registrations,
                created,
            ),
            registrations=registrations,
            created=created,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.registrations, tuple) or not self.registrations:
            raise ValueError(
                "processing registrations must be a nonempty tuple"
            )
        if len(self.registrations) > _MAX_BOOKS:
            raise ValueError("processing registration count exceeds the bound")
        if any(
            type(item) is not ProcessingBookRegistration
            for item in self.registrations
        ):
            raise TypeError("registrations contain an unsupported value")
        if sum(item.chunks for item in self.registrations) > _MAX_CHUNKS:
            raise ValueError("processing registrations exceed the chunk bound")
        if len({item.name for item in self.registrations}) != len(
            self.registrations
        ):
            raise ValueError("processing registration names must be unique")
        if len({item.queue_order for item in self.registrations}) != len(
            self.registrations
        ):
            raise ValueError(
                "processing registration queue order must be unique"
            )
        _finite_nonnegative("initialization created", self.created)
        expected = stable_id(
            "processing-state-initialization-request",
            self.CONTRACT_VERSION,
            self.registrations,
            self.created,
        )
        if self.request_id != expected:
            raise ValueError(
                "processing initialization request ID is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class ProcessingStateLoadRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bound one state read to the exact expected queue members."""

    CONTRACT_NAME: ClassVar[str] = "processing-state-load-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    book_names: tuple[str, ...]

    @classmethod
    def create(
        cls, *, book_names: tuple[str, ...]
    ) -> ProcessingStateLoadRequest:
        return cls(
            request_id=stable_id(
                "processing-state-load-request",
                cls.CONTRACT_VERSION,
                book_names,
            ),
            book_names=book_names,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.book_names, tuple) or not self.book_names:
            raise ValueError("book_names must be a nonempty tuple")
        if len(self.book_names) > _MAX_BOOKS:
            raise ValueError("book_names exceed the bound")
        for value in self.book_names:
            _bounded_string("book name", value)
        if len(set(self.book_names)) != len(self.book_names):
            raise ValueError("book_names must be unique")
        expected = stable_id(
            "processing-state-load-request",
            self.CONTRACT_VERSION,
            self.book_names,
        )
        if self.request_id != expected:
            raise ValueError("processing state load request ID is inconsistent")


@dataclass(frozen=True, slots=True)
class ProcessingStateSaveRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Optimistically commit one exact complete checkpoint transition."""

    CONTRACT_NAME: ClassVar[str] = "processing-state-save-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    expected_snapshot_id: str
    snapshot: ProcessingStateSnapshot
    events: tuple[ProcessingEventDraft, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        expected_snapshot_id: str,
        snapshot: ProcessingStateSnapshot,
        events: tuple[ProcessingEventDraft, ...] = (),
    ) -> ProcessingStateSaveRequest:
        return cls(
            request_id=stable_id(
                "processing-state-save-request",
                cls.CONTRACT_VERSION,
                expected_snapshot_id,
                snapshot.snapshot_id,
                events,
            ),
            expected_snapshot_id=expected_snapshot_id,
            snapshot=snapshot,
            events=events,
        )

    def __post_init__(self) -> None:
        if not re.fullmatch(
            r"processing-state-snapshot:sha256:[0-9a-f]{64}",
            self.expected_snapshot_id,
        ):
            raise ValueError("expected processing snapshot ID is invalid")
        if type(self.snapshot) is not ProcessingStateSnapshot:
            raise TypeError("snapshot must be a ProcessingStateSnapshot")
        if (
            not isinstance(self.events, tuple)
            or len(self.events) > _MAX_EVENTS_PER_SAVE
        ):
            raise ValueError("processing save events exceed the bound")
        if any(type(item) is not ProcessingEventDraft for item in self.events):
            raise TypeError("events contain an unsupported value")
        if len({item.event_id for item in self.events}) != len(self.events):
            raise ValueError("processing event IDs must be unique")
        known_books = {book.name for book in self.snapshot.books}
        if any(event.book not in known_books for event in self.events):
            raise ValueError("processing event refers to an unknown book")
        expected = stable_id(
            "processing-state-save-request",
            self.CONTRACT_VERSION,
            self.expected_snapshot_id,
            self.snapshot.snapshot_id,
            self.events,
        )
        if self.request_id != expected:
            raise ValueError("processing state save request ID is inconsistent")


@dataclass(frozen=True, slots=True)
class ProcessingStateSaveResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Outcome and exact snapshot for one processing state commit."""

    CONTRACT_NAME: ClassVar[str] = "processing-state-save-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    snapshot: ProcessingStateSnapshot
    status: ProcessingStateSaveStatus
    event_count: int

    def __post_init__(self) -> None:
        _bounded_string(
            "request ID", self.request_id, maximum=_MAX_LABEL_CHARACTERS
        )
        if type(self.snapshot) is not ProcessingStateSnapshot:
            raise TypeError("snapshot must be a ProcessingStateSnapshot")
        if not isinstance(self.status, ProcessingStateSaveStatus):
            raise TypeError("status must be a ProcessingStateSaveStatus")
        _nonnegative_integer("event_count", self.event_count)
        if self.event_count > _MAX_EVENTS_PER_SAVE:
            raise ValueError("event_count exceeds the bound")
