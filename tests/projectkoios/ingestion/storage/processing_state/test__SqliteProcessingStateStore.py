from __future__ import annotations

import os
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from projectkoios.ingestion.integrations.sqlite.processing_state.store import (
    SqliteProcessingStateStore,
)
from projectkoios.ingestion.storage.processing_state.base import (
    AbstractProcessingStateStore,
)
from projectkoios.ingestion.storage.processing_state.contracts import (
    ProcessingBookRegistration,
    ProcessingEventDraft,
    ProcessingStateInitializationRequest,
    ProcessingStateLoadRequest,
    ProcessingStateSaveRequest,
    ProcessingStateSaveStatus,
    ProcessingStateSnapshot,
)
from projectkoios.ingestion.storage.processing_state.error import (
    ProcessingStateConflictError,
    ProcessingStateStoreError,
)


def _initialize(
    tmp_path: Path,
    registration: ProcessingBookRegistration,
) -> tuple[SqliteProcessingStateStore, ProcessingStateSnapshot]:
    tmp_path.chmod(0o700)
    store = SqliteProcessingStateStore(database=tmp_path / "state.sqlite3")
    snapshot = store.initialize(
        request=ProcessingStateInitializationRequest.create(
            registrations=(registration,),
            created=1.0,
        )
    )
    return store, snapshot


def test__sqlite_processing_state_store__owns_exact_checkpoint_round_trip(
    tmp_path: Path,
    registration: ProcessingBookRegistration,
    detected_snapshot: ProcessingStateSnapshot,
) -> None:
    store, initial = _initialize(tmp_path, registration)
    event = ProcessingEventDraft.create(
        created=2.0,
        book=registration.name,
        label="Detected",
        detail="one sanitized candidate",
    )
    request = ProcessingStateSaveRequest.create(
        expected_snapshot_id=initial.snapshot_id,
        snapshot=detected_snapshot,
        events=(event,),
    )

    committed = store.save(request=request)
    replayed = store.save(request=request)
    loaded = store.load(
        request=ProcessingStateLoadRequest.create(
            book_names=(registration.name,)
        )
    )

    assert isinstance(store, AbstractProcessingStateStore)
    assert committed.status is ProcessingStateSaveStatus.COMMITTED
    assert replayed.status is ProcessingStateSaveStatus.UNCHANGED
    assert loaded == detected_snapshot
    assert stat_mode(tmp_path / "state.sqlite3") == 0o600
    assert not hasattr(store, "execute")
    with sqlite3.connect(tmp_path / "state.sqlite3") as connection:
        assert (
            connection.execute("SELECT count(*) FROM events").fetchone()[0] == 1
        )


def test__sqlite_processing_state_store__reports_exact_noop_as_unchanged(
    tmp_path: Path,
    registration: ProcessingBookRegistration,
) -> None:
    store, initial = _initialize(tmp_path, registration)

    result = store.save(
        request=ProcessingStateSaveRequest.create(
            expected_snapshot_id=initial.snapshot_id,
            snapshot=initial,
        )
    )

    assert result.status is ProcessingStateSaveStatus.UNCHANGED
    assert result.snapshot == initial


def test__sqlite_processing_state_store__rejects_stale_conflicting_save(
    tmp_path: Path,
    registration: ProcessingBookRegistration,
    detected_snapshot: ProcessingStateSnapshot,
) -> None:
    store, initial = _initialize(tmp_path, registration)
    store.save(
        request=ProcessingStateSaveRequest.create(
            expected_snapshot_id=initial.snapshot_id,
            snapshot=detected_snapshot,
        )
    )
    conflicting = ProcessingStateSnapshot.create(
        books=(replace(detected_snapshot.books[0], stage="different"),),
        chunks=detected_snapshot.chunks,
        candidates=detected_snapshot.candidates,
    )

    with pytest.raises(ProcessingStateConflictError, match="changed"):
        store.save(
            request=ProcessingStateSaveRequest.create(
                expected_snapshot_id=initial.snapshot_id,
                snapshot=conflicting,
            )
        )


def test__sqlite_processing_state_store__migrates_legacy_event_identity(
    tmp_path: Path,
    registration: ProcessingBookRegistration,
) -> None:
    tmp_path.chmod(0o700)
    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE books (
          name TEXT PRIMARY KEY, queue_order INTEGER NOT NULL,
          pages INTEGER NOT NULL, chunks INTEGER NOT NULL,
          stage TEXT NOT NULL DEFAULT 'pending',
          state TEXT NOT NULL DEFAULT 'pending',
          equation_candidates INTEGER NOT NULL DEFAULT 0,
          figure_candidates INTEGER NOT NULL DEFAULT 0,
          primary_equations INTEGER NOT NULL DEFAULT 0,
          paragraphs INTEGER NOT NULL DEFAULT 0,
          runtime_seconds REAL NOT NULL DEFAULT 0,
          error TEXT, updated REAL NOT NULL
        );
        CREATE TABLE chunks (
          book TEXT NOT NULL, chunk_number INTEGER NOT NULL,
          first_page INTEGER NOT NULL, last_page INTEGER NOT NULL,
          detection_state TEXT NOT NULL DEFAULT 'pending',
          equation_state TEXT NOT NULL DEFAULT 'pending',
          equation_count INTEGER NOT NULL DEFAULT 0,
          figure_count INTEGER NOT NULL DEFAULT 0,
          detection_seconds REAL, equation_seconds REAL,
          error TEXT, updated REAL NOT NULL,
          PRIMARY KEY(book, chunk_number)
        );
        CREATE TABLE candidates (
          book TEXT NOT NULL, kind TEXT NOT NULL,
          chunk_number INTEGER NOT NULL, ordinal INTEGER NOT NULL,
          label TEXT NOT NULL, source_page INTEGER NOT NULL,
          owner_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'detected',
          runtime_seconds REAL, error TEXT, artifact_path TEXT NOT NULL,
          updated REAL NOT NULL,
          PRIMARY KEY(book, kind, chunk_number, ordinal)
        );
        CREATE TABLE events (
          event_number INTEGER PRIMARY KEY AUTOINCREMENT,
          created REAL NOT NULL, book TEXT NOT NULL,
          label TEXT NOT NULL, detail TEXT NOT NULL
        );
        INSERT INTO events(created, book, label, detail)
        VALUES(0.5, 'sanitized-book', 'Legacy', 'retained');
        """
    )
    connection.commit()
    connection.close()
    database.chmod(0o600)

    store = SqliteProcessingStateStore(database=database)
    store.initialize(
        request=ProcessingStateInitializationRequest.create(
            registrations=(registration,),
            created=1.0,
        )
    )

    with sqlite3.connect(database) as verified:
        columns = {
            row[1]
            for row in verified.execute("PRAGMA table_info(events)").fetchall()
        }
        event_id = verified.execute(
            "SELECT event_id FROM events WHERE event_number=1"
        ).fetchone()[0]
    assert "event_id" in columns
    assert event_id.startswith("legacy-processing-event:sha256:")


def test__sqlite_processing_state_store__rejects_unsafe_database_path(
    tmp_path: Path,
    registration: ProcessingBookRegistration,
) -> None:
    tmp_path.chmod(0o700)
    target = tmp_path / "target.sqlite3"
    target.write_bytes(b"not a database")
    target.chmod(0o600)
    alias = tmp_path / "state.sqlite3"
    alias.symlink_to(target)
    store = SqliteProcessingStateStore(database=alias)

    with pytest.raises(ProcessingStateStoreError, match="regular file"):
        store.initialize(
            request=ProcessingStateInitializationRequest.create(
                registrations=(registration,),
                created=1.0,
            )
        )


def stat_mode(path: Path) -> int:
    return os.stat(path, follow_symlinks=False).st_mode & 0o777
