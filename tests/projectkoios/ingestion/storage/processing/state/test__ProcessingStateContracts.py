from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest
from projectkoios.base import DataObjectActionRequest, DataObjectActionResult
from projectkoios.ingestion.storage.processing.state.contracts import (
    ProcessingBookRegistration,
    ProcessingEventDraft,
    ProcessingStateInitializationRequest,
    ProcessingStateLoadRequest,
    ProcessingStateSaveRequest,
    ProcessingStateSaveResult,
    ProcessingStateSaveStatus,
    ProcessingStateSnapshot,
)


def test__processing_state_contracts__use_nominal_request_result_boundaries(
    pending_snapshot: ProcessingStateSnapshot,
    detected_snapshot: ProcessingStateSnapshot,
    registration: ProcessingBookRegistration,
) -> None:
    initialization = ProcessingStateInitializationRequest.create(
        registrations=(registration,),
        created=1.0,
    )
    load = ProcessingStateLoadRequest.create(book_names=(registration.name,))
    event = ProcessingEventDraft.create(
        created=2.0,
        book=registration.name,
        label="Detected",
        detail="one sanitized candidate",
    )
    save = ProcessingStateSaveRequest.create(
        expected_snapshot_id=pending_snapshot.snapshot_id,
        snapshot=detected_snapshot,
        events=(event,),
    )
    result = ProcessingStateSaveResult(
        request_id=save.request_id,
        snapshot=detected_snapshot,
        status=ProcessingStateSaveStatus.COMMITTED,
        event_count=1,
    )

    assert isinstance(initialization, DataObjectActionRequest)
    assert isinstance(load, DataObjectActionRequest)
    assert isinstance(save, DataObjectActionRequest)
    assert isinstance(result, DataObjectActionResult)
    assert event.event_id.startswith("processing-event:sha256:")
    with pytest.raises(FrozenInstanceError):
        detected_snapshot.snapshot_id = "changed"  # type: ignore[misc]


def test__processing_state_snapshot__rejects_incomplete_or_inconsistent_state(
    pending_snapshot: ProcessingStateSnapshot,
) -> None:
    with pytest.raises(ValueError, match="chunk inventory"):
        ProcessingStateSnapshot.create(
            books=pending_snapshot.books,
            chunks=pending_snapshot.chunks[:1],
            candidates=(),
        )

    inconsistent = replace(pending_snapshot.books[0], equation_candidates=1)
    with pytest.raises(ValueError, match="equation candidate count"):
        ProcessingStateSnapshot.create(
            books=(inconsistent,),
            chunks=pending_snapshot.chunks,
            candidates=(),
        )


def test__processing_state_requests__reject_unknown_event_books(
    pending_snapshot: ProcessingStateSnapshot,
) -> None:
    event = ProcessingEventDraft.create(
        created=2.0,
        book="unknown-book",
        label="Invalid",
        detail="must fail closed",
    )
    with pytest.raises(ValueError, match="unknown book"):
        ProcessingStateSaveRequest.create(
            expected_snapshot_id=pending_snapshot.snapshot_id,
            snapshot=pending_snapshot,
            events=(event,),
        )
