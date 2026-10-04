"""Ownership check for the internal reconciliation candidate."""

from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion.reconciliation._candidate import _Candidate
from projectkoios.ingestion.reconciliation.match_kind import (
    OCRReconciliationMatchKind,
)


def test___Candidate__is_frozen_and_owned_by_its_module() -> None:
    candidate = _Candidate(
        "native",
        "ocr",
        OCRReconciliationMatchKind.DUPLICATE,
        1.0,
        1.0,
        1.0,
        0,
        0,
    )
    assert (
        _Candidate.__module__
        == "projectkoios.ingestion.reconciliation._candidate"
    )
    with pytest.raises(FrozenInstanceError):
        candidate.score = 0.5  # type: ignore[misc]
