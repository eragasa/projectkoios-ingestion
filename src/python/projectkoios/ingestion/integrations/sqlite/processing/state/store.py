"""SQLite projection for backend-neutral bounded processing checkpoints."""

from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.processing.state.base import (
    AbstractProcessingStateStore,
)
from projectkoios.ingestion.storage.processing.state.contracts import (
    ProcessingBookRegistration,
    ProcessingBookState,
    ProcessingCandidateState,
    ProcessingChunkState,
    ProcessingEventDraft,
    ProcessingStateInitializationRequest,
    ProcessingStateLoadRequest,
    ProcessingStateSaveRequest,
    ProcessingStateSaveResult,
    ProcessingStateSaveStatus,
    ProcessingStateSnapshot,
)
from projectkoios.ingestion.storage.processing.state.error import (
    ProcessingStateConflictError,
    ProcessingStateStoreError,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
  name TEXT PRIMARY KEY,
  queue_order INTEGER NOT NULL UNIQUE,
  pages INTEGER NOT NULL,
  chunks INTEGER NOT NULL,
  stage TEXT NOT NULL DEFAULT 'pending',
  state TEXT NOT NULL DEFAULT 'pending',
  equation_candidates INTEGER NOT NULL DEFAULT 0,
  figure_candidates INTEGER NOT NULL DEFAULT 0,
  primary_equations INTEGER NOT NULL DEFAULT 0,
  paragraphs INTEGER NOT NULL DEFAULT 0,
  runtime_seconds REAL NOT NULL DEFAULT 0,
  error TEXT,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  book TEXT NOT NULL,
  chunk_number INTEGER NOT NULL,
  first_page INTEGER NOT NULL,
  last_page INTEGER NOT NULL,
  detection_state TEXT NOT NULL DEFAULT 'pending',
  equation_state TEXT NOT NULL DEFAULT 'pending',
  equation_count INTEGER NOT NULL DEFAULT 0,
  figure_count INTEGER NOT NULL DEFAULT 0,
  detection_seconds REAL,
  equation_seconds REAL,
  error TEXT,
  updated REAL NOT NULL,
  PRIMARY KEY(book, chunk_number),
  FOREIGN KEY(book) REFERENCES books(name)
);
CREATE TABLE IF NOT EXISTS candidates (
  book TEXT NOT NULL,
  kind TEXT NOT NULL,
  chunk_number INTEGER NOT NULL,
  ordinal INTEGER NOT NULL,
  label TEXT NOT NULL,
  source_page INTEGER NOT NULL,
  owner_id TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'detected',
  runtime_seconds REAL,
  error TEXT,
  artifact_path TEXT NOT NULL,
  updated REAL NOT NULL,
  PRIMARY KEY(book, kind, chunk_number, ordinal),
  FOREIGN KEY(book, chunk_number) REFERENCES chunks(book, chunk_number)
);
CREATE TABLE IF NOT EXISTS events (
  event_number INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE,
  created REAL NOT NULL,
  book TEXT NOT NULL,
  label TEXT NOT NULL,
  detail TEXT NOT NULL,
  FOREIGN KEY(book) REFERENCES books(name)
);
"""


class SqliteProcessingStateStore(AbstractProcessingStateStore):
    """Own every SQLite connection, statement, cursor, row, and transaction."""

    def __init__(self, *, database: Path) -> None:
        if not isinstance(database, Path):
            raise TypeError("database must be a pathlib.Path")
        self.database = Path(os.path.abspath(database.expanduser()))

    def initialize(
        self, *, request: ProcessingStateInitializationRequest
    ) -> ProcessingStateSnapshot:
        if type(request) is not ProcessingStateInitializationRequest:
            raise TypeError(
                "request must be a ProcessingStateInitializationRequest"
            )
        self._prepare_database_parent()
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect(require_existing=False)
            connection.executescript(_SCHEMA)
            self._migrate_event_identity(connection)
            for registration in request.registrations:
                self._initialize_book(
                    connection,
                    registration=registration,
                    created=request.created,
                )
            connection.commit()
            snapshot = self._read_snapshot(
                connection,
                tuple(item.name for item in request.registrations),
            )
            self._validate_registrations(snapshot, request.registrations)
            os.chmod(self.database, 0o600)
            return snapshot
        except (OSError, sqlite3.Error) as error:
            raise ProcessingStateStoreError(
                "SQLite processing state initialization failed"
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def load(
        self, *, request: ProcessingStateLoadRequest
    ) -> ProcessingStateSnapshot:
        if type(request) is not ProcessingStateLoadRequest:
            raise TypeError("request must be a ProcessingStateLoadRequest")
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect(require_existing=True)
            return self._read_snapshot(connection, request.book_names)
        except ProcessingStateStoreError:
            raise
        except (OSError, sqlite3.Error) as error:
            raise ProcessingStateStoreError(
                "SQLite processing state load failed"
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def save(
        self, *, request: ProcessingStateSaveRequest
    ) -> ProcessingStateSaveResult:
        if type(request) is not ProcessingStateSaveRequest:
            raise TypeError("request must be a ProcessingStateSaveRequest")
        book_names = tuple(book.name for book in request.snapshot.books)
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect(require_existing=True)
            connection.execute("BEGIN IMMEDIATE")
            current = self._read_snapshot(connection, book_names)
            if current == request.snapshot and self._events_are_exact(
                connection, request.events
            ):
                connection.rollback()
                return ProcessingStateSaveResult(
                    request_id=request.request_id,
                    snapshot=current,
                    status=ProcessingStateSaveStatus.UNCHANGED,
                    event_count=len(request.events),
                )
            if current.snapshot_id != request.expected_snapshot_id:
                raise ProcessingStateConflictError(
                    "processing state changed before the requested save"
                )
            self._validate_transition(current, request.snapshot)
            self._write_books(
                connection,
                current=current.books,
                intended=request.snapshot.books,
            )
            self._write_chunks(
                connection,
                current=current.chunks,
                intended=request.snapshot.chunks,
            )
            self._write_candidates(
                connection,
                current=current.candidates,
                intended=request.snapshot.candidates,
            )
            self._append_events(connection, request.events)
            committed = self._read_snapshot(connection, book_names)
            if committed != request.snapshot:
                raise ProcessingStateStoreError(
                    "SQLite processing state did not replay after save"
                )
            connection.commit()
            return ProcessingStateSaveResult(
                request_id=request.request_id,
                snapshot=committed,
                status=ProcessingStateSaveStatus.COMMITTED,
                event_count=len(request.events),
            )
        except ProcessingStateConflictError:
            if connection is not None:
                connection.rollback()
            raise
        except ProcessingStateStoreError:
            if connection is not None:
                connection.rollback()
            raise
        except (OSError, sqlite3.Error) as error:
            if connection is not None:
                connection.rollback()
            raise ProcessingStateStoreError(
                "SQLite processing state save failed"
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def _connect(self, *, require_existing: bool) -> sqlite3.Connection:
        if os.path.lexists(self.database):
            file_status = os.lstat(self.database)
            if stat.S_ISLNK(file_status.st_mode) or not stat.S_ISREG(
                file_status.st_mode
            ):
                raise ProcessingStateStoreError(
                    "processing state database is not a regular file"
                )
            if stat.S_IMODE(file_status.st_mode) & 0o077:
                raise ProcessingStateStoreError(
                    "processing state database is not private"
                )
        elif require_existing:
            raise ProcessingStateStoreError(
                "processing state database does not exist"
            )
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.database, flags, 0o600)
            os.close(descriptor)
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _prepare_database_parent(self) -> None:
        parent = self.database.parent
        if os.path.lexists(parent):
            parent_status = os.lstat(parent)
            if stat.S_ISLNK(parent_status.st_mode) or not stat.S_ISDIR(
                parent_status.st_mode
            ):
                raise ProcessingStateStoreError(
                    "processing state parent is not a real directory"
                )
            if stat.S_IMODE(parent_status.st_mode) & 0o077:
                raise ProcessingStateStoreError(
                    "processing state parent is not private"
                )
            return
        parent.mkdir(parents=True, mode=0o700)
        os.chmod(parent, 0o700)

    @staticmethod
    def _migrate_event_identity(connection: sqlite3.Connection) -> None:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(events)"
            ).fetchall()
        }
        if "event_id" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN event_id TEXT")
        rows = connection.execute(
            "SELECT event_number, created, book, label, detail "
            "FROM events WHERE event_id IS NULL ORDER BY event_number"
        ).fetchall()
        for row in rows:
            event_id = stable_id(
                "legacy-processing-event",
                int(row["event_number"]),
                float(row["created"]),
                str(row["book"]),
                str(row["label"]),
                str(row["detail"]),
            )
            connection.execute(
                "UPDATE events SET event_id=? WHERE event_number=? "
                "AND event_id IS NULL",
                (event_id, int(row["event_number"])),
            )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS events_event_id_unique "
            "ON events(event_id)"
        )

    @staticmethod
    def _initialize_book(
        connection: sqlite3.Connection,
        *,
        registration: ProcessingBookRegistration,
        created: float,
    ) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO books"
            "(name, queue_order, pages, chunks, updated) VALUES(?,?,?,?,?)",
            (
                registration.name,
                registration.queue_order,
                registration.pages,
                registration.chunks,
                created,
            ),
        )
        for chunk_number in range(1, registration.chunks + 1):
            first_page = (chunk_number - 1) * registration.chunk_pages + 1
            last_page = min(
                registration.pages,
                first_page + registration.chunk_pages - 1,
            )
            connection.execute(
                "INSERT OR IGNORE INTO chunks"
                "(book, chunk_number, first_page, last_page, updated) "
                "VALUES(?,?,?,?,?)",
                (
                    registration.name,
                    chunk_number,
                    first_page,
                    last_page,
                    created,
                ),
            )

    @staticmethod
    def _validate_registrations(
        snapshot: ProcessingStateSnapshot,
        registrations: tuple[ProcessingBookRegistration, ...],
    ) -> None:
        expected_books = {
            registration.name: registration for registration in registrations
        }
        for book in snapshot.books:
            registration = expected_books.get(book.name)
            if registration is None or (
                book.queue_order,
                book.pages,
                book.chunks,
            ) != (
                registration.queue_order,
                registration.pages,
                registration.chunks,
            ):
                raise ProcessingStateConflictError(
                    "existing processing queue registration differs"
                )
        chunk_by_book: dict[str, list[ProcessingChunkState]] = {}
        for chunk in snapshot.chunks:
            chunk_by_book.setdefault(chunk.book, []).append(chunk)
        for registration in registrations:
            actual = chunk_by_book.get(registration.name, [])
            expected = [
                (
                    number,
                    (number - 1) * registration.chunk_pages + 1,
                    min(
                        registration.pages,
                        number * registration.chunk_pages,
                    ),
                )
                for number in range(1, registration.chunks + 1)
            ]
            if [
                (chunk.chunk_number, chunk.first_page, chunk.last_page)
                for chunk in actual
            ] != expected:
                raise ProcessingStateConflictError(
                    "existing processing chunk registration differs"
                )

    @staticmethod
    def _read_snapshot(
        connection: sqlite3.Connection,
        book_names: tuple[str, ...],
    ) -> ProcessingStateSnapshot:
        book_rows = connection.execute(
            "SELECT name, queue_order, pages, chunks, stage, state, "
            "equation_candidates, figure_candidates, primary_equations, "
            "paragraphs, runtime_seconds, error, updated "
            "FROM books ORDER BY queue_order"
        ).fetchall()
        if tuple(str(row["name"]) for row in book_rows) != book_names:
            raise ProcessingStateConflictError(
                "processing state book inventory differs from the request"
            )
        books = tuple(
            ProcessingBookState(
                name=str(row["name"]),
                queue_order=int(row["queue_order"]),
                pages=int(row["pages"]),
                chunks=int(row["chunks"]),
                stage=str(row["stage"]),
                state=str(row["state"]),
                equation_candidates=int(row["equation_candidates"]),
                figure_candidates=int(row["figure_candidates"]),
                primary_equations=int(row["primary_equations"]),
                paragraphs=int(row["paragraphs"]),
                runtime_seconds=float(row["runtime_seconds"]),
                error=(None if row["error"] is None else str(row["error"])),
                updated=float(row["updated"]),
            )
            for row in book_rows
        )
        chunk_rows = connection.execute(
            "SELECT book, chunk_number, first_page, last_page, "
            "detection_state, equation_state, equation_count, figure_count, "
            "detection_seconds, equation_seconds, error, updated "
            "FROM chunks ORDER BY book, chunk_number"
        ).fetchall()
        chunks = tuple(
            ProcessingChunkState(
                book=str(row["book"]),
                chunk_number=int(row["chunk_number"]),
                first_page=int(row["first_page"]),
                last_page=int(row["last_page"]),
                detection_state=str(row["detection_state"]),
                equation_state=str(row["equation_state"]),
                equation_count=int(row["equation_count"]),
                figure_count=int(row["figure_count"]),
                detection_seconds=(
                    None
                    if row["detection_seconds"] is None
                    else float(row["detection_seconds"])
                ),
                equation_seconds=(
                    None
                    if row["equation_seconds"] is None
                    else float(row["equation_seconds"])
                ),
                error=(None if row["error"] is None else str(row["error"])),
                updated=float(row["updated"]),
            )
            for row in chunk_rows
        )
        candidate_rows = connection.execute(
            "SELECT book, kind, chunk_number, ordinal, label, source_page, "
            "owner_id, state, runtime_seconds, error, artifact_path, updated "
            "FROM candidates ORDER BY book, kind, chunk_number, ordinal"
        ).fetchall()
        candidates = tuple(
            ProcessingCandidateState(
                book=str(row["book"]),
                kind=str(row["kind"]),
                chunk_number=int(row["chunk_number"]),
                ordinal=int(row["ordinal"]),
                label=str(row["label"]),
                source_page=int(row["source_page"]),
                owner_id=str(row["owner_id"]),
                state=str(row["state"]),
                runtime_seconds=(
                    None
                    if row["runtime_seconds"] is None
                    else float(row["runtime_seconds"])
                ),
                error=(None if row["error"] is None else str(row["error"])),
                artifact_path=str(row["artifact_path"]),
                updated=float(row["updated"]),
            )
            for row in candidate_rows
        )
        return ProcessingStateSnapshot.create(
            books=books,
            chunks=chunks,
            candidates=candidates,
        )

    @staticmethod
    def _validate_transition(
        current: ProcessingStateSnapshot,
        intended: ProcessingStateSnapshot,
    ) -> None:
        current_books = {
            book.name: (book.queue_order, book.pages, book.chunks)
            for book in current.books
        }
        intended_books = {
            book.name: (book.queue_order, book.pages, book.chunks)
            for book in intended.books
        }
        if current_books != intended_books:
            raise ProcessingStateConflictError(
                "processing book registration cannot change during save"
            )
        current_chunks = {
            (chunk.book, chunk.chunk_number): (
                chunk.first_page,
                chunk.last_page,
            )
            for chunk in current.chunks
        }
        intended_chunks = {
            (chunk.book, chunk.chunk_number): (
                chunk.first_page,
                chunk.last_page,
            )
            for chunk in intended.chunks
        }
        if current_chunks != intended_chunks:
            raise ProcessingStateConflictError(
                "processing chunk registration cannot change during save"
            )

    @staticmethod
    def _write_books(
        connection: sqlite3.Connection,
        *,
        current: tuple[ProcessingBookState, ...],
        intended: tuple[ProcessingBookState, ...],
    ) -> None:
        current_by_name = {book.name: book for book in current}
        changed = tuple(
            book for book in intended if current_by_name.get(book.name) != book
        )
        connection.executemany(
            "UPDATE books SET stage=?, state=?, equation_candidates=?, "
            "figure_candidates=?, primary_equations=?, paragraphs=?, "
            "runtime_seconds=?, error=?, updated=? WHERE name=?",
            tuple(
                (
                    book.stage,
                    book.state,
                    book.equation_candidates,
                    book.figure_candidates,
                    book.primary_equations,
                    book.paragraphs,
                    book.runtime_seconds,
                    book.error,
                    book.updated,
                    book.name,
                )
                for book in changed
            ),
        )

    @staticmethod
    def _write_chunks(
        connection: sqlite3.Connection,
        *,
        current: tuple[ProcessingChunkState, ...],
        intended: tuple[ProcessingChunkState, ...],
    ) -> None:
        current_by_key = {
            (chunk.book, chunk.chunk_number): chunk for chunk in current
        }
        changed = tuple(
            chunk
            for chunk in intended
            if current_by_key.get((chunk.book, chunk.chunk_number)) != chunk
        )
        connection.executemany(
            "UPDATE chunks SET detection_state=?, equation_state=?, "
            "equation_count=?, figure_count=?, detection_seconds=?, "
            "equation_seconds=?, error=?, updated=? "
            "WHERE book=? AND chunk_number=?",
            tuple(
                (
                    chunk.detection_state,
                    chunk.equation_state,
                    chunk.equation_count,
                    chunk.figure_count,
                    chunk.detection_seconds,
                    chunk.equation_seconds,
                    chunk.error,
                    chunk.updated,
                    chunk.book,
                    chunk.chunk_number,
                )
                for chunk in changed
            ),
        )

    @staticmethod
    def _write_candidates(
        connection: sqlite3.Connection,
        *,
        current: tuple[ProcessingCandidateState, ...],
        intended: tuple[ProcessingCandidateState, ...],
    ) -> None:
        current_by_key = {item.key: item for item in current}
        intended_by_key = {item.key: item for item in intended}
        for candidate in current:
            if candidate.key not in intended_by_key:
                connection.execute(
                    "DELETE FROM candidates WHERE book=? AND kind=? "
                    "AND chunk_number=? AND ordinal=?",
                    candidate.key,
                )
        connection.executemany(
            "INSERT INTO candidates"
            "(book, kind, chunk_number, ordinal, label, source_page, owner_id, "
            "state, runtime_seconds, error, artifact_path, updated) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(book, kind, chunk_number, ordinal) DO UPDATE SET "
            "label=excluded.label, source_page=excluded.source_page, "
            "owner_id=excluded.owner_id, state=excluded.state, "
            "runtime_seconds=excluded.runtime_seconds, error=excluded.error, "
            "artifact_path=excluded.artifact_path, updated=excluded.updated",
            tuple(
                (
                    item.book,
                    item.kind,
                    item.chunk_number,
                    item.ordinal,
                    item.label,
                    item.source_page,
                    item.owner_id,
                    item.state,
                    item.runtime_seconds,
                    item.error,
                    item.artifact_path,
                    item.updated,
                )
                for item in intended
                if current_by_key.get(item.key) != item
            ),
        )

    @staticmethod
    def _append_events(
        connection: sqlite3.Connection,
        events: tuple[ProcessingEventDraft, ...],
    ) -> None:
        for event in events:
            existing = connection.execute(
                "SELECT created, book, label, detail FROM events "
                "WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
            if existing is not None:
                if (
                    float(existing["created"]),
                    str(existing["book"]),
                    str(existing["label"]),
                    str(existing["detail"]),
                ) != (event.created, event.book, event.label, event.detail):
                    raise ProcessingStateConflictError(
                        "processing event identity is conflicting"
                    )
                continue
            connection.execute(
                "INSERT INTO events(event_id, created, book, label, detail) "
                "VALUES(?,?,?,?,?)",
                (
                    event.event_id,
                    event.created,
                    event.book,
                    event.label,
                    event.detail,
                ),
            )

    @classmethod
    def _events_are_exact(
        cls,
        connection: sqlite3.Connection,
        events: tuple[ProcessingEventDraft, ...],
    ) -> bool:
        for event in events:
            row = connection.execute(
                "SELECT created, book, label, detail FROM events "
                "WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
            if row is None or (
                float(row["created"]),
                str(row["book"]),
                str(row["label"]),
                str(row["detail"]),
            ) != (event.created, event.book, event.label, event.detail):
                return False
        return True
