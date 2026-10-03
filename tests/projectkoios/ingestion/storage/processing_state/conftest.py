from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.storage.processing_state.contracts import (
    ProcessingBookRegistration,
    ProcessingBookState,
    ProcessingCandidateState,
    ProcessingChunkState,
    ProcessingStateSnapshot,
)


@pytest.fixture
def registration() -> ProcessingBookRegistration:
    return ProcessingBookRegistration(
        name="sanitized-book",
        queue_order=1,
        pages=3,
        chunk_pages=2,
    )


@pytest.fixture
def pending_snapshot() -> ProcessingStateSnapshot:
    return ProcessingStateSnapshot.create(
        books=(
            ProcessingBookState(
                name="sanitized-book",
                queue_order=1,
                pages=3,
                chunks=2,
                stage="pending",
                state="pending",
                equation_candidates=0,
                figure_candidates=0,
                primary_equations=0,
                paragraphs=0,
                runtime_seconds=0.0,
                error=None,
                updated=1.0,
            ),
        ),
        chunks=(
            ProcessingChunkState(
                book="sanitized-book",
                chunk_number=1,
                first_page=1,
                last_page=2,
                detection_state="pending",
                equation_state="pending",
                equation_count=0,
                figure_count=0,
                detection_seconds=None,
                equation_seconds=None,
                error=None,
                updated=1.0,
            ),
            ProcessingChunkState(
                book="sanitized-book",
                chunk_number=2,
                first_page=3,
                last_page=3,
                detection_state="pending",
                equation_state="pending",
                equation_count=0,
                figure_count=0,
                detection_seconds=None,
                equation_seconds=None,
                error=None,
                updated=1.0,
            ),
        ),
        candidates=(),
    )


@pytest.fixture
def detected_snapshot(
    pending_snapshot: ProcessingStateSnapshot,
) -> ProcessingStateSnapshot:
    chunk = replace(
        pending_snapshot.chunks[0],
        detection_state="complete",
        equation_count=1,
        detection_seconds=0.25,
        updated=2.0,
    )
    book = replace(
        pending_snapshot.books[0],
        stage="detection",
        state="running",
        equation_candidates=1,
        updated=2.0,
    )
    candidate = ProcessingCandidateState(
        book="sanitized-book",
        kind="equation",
        chunk_number=1,
        ordinal=1,
        label="Equation p1-1",
        source_page=1,
        owner_id="equation:fixture:one",
        state="detected",
        runtime_seconds=None,
        error=None,
        artifact_path="chunks/chunk-001/equations/equation-001",
        updated=2.0,
    )
    return ProcessingStateSnapshot.create(
        books=(book,),
        chunks=(chunk, pending_snapshot.chunks[1]),
        candidates=(candidate,),
    )
