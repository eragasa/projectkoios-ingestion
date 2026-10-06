from __future__ import annotations

from projectkoios.ingestion.storage.processing.state.base import (
    AbstractProcessingStateStore,
)


def test__abstract_processing_state_store__requires_all_state_operations() -> (
    None
):
    assert AbstractProcessingStateStore.__abstractmethods__ == {
        "initialize",
        "load",
        "save",
    }
