from pathlib import Path

import pytest
from projectkoios.ingestion.equation_enrichment import (
    EquationEnrichmentInventoryError,
    EquationEnrichmentInventoryStatus,
    EquationRecognitionCheckpoint,
    EquationRecognitionWorkState,
    defer_equation_recognition,
    inspect_equation_enrichment_inventory,
    require_equation_enrichment_inventory,
)


def test__enrichment_inventory__distinguishes_none_complete_and_partial(
    tmp_path: Path,
) -> None:
    root = tmp_path / "enrichment"
    root.mkdir()

    empty = require_equation_enrichment_inventory(root)
    assert empty.status is EquationEnrichmentInventoryStatus.NONE

    (root / "recognition.json").write_text("{}", encoding="utf-8")
    partial = inspect_equation_enrichment_inventory(root)
    assert partial.status is EquationEnrichmentInventoryStatus.PARTIAL
    assert partial.problem_codes == ("index_missing",)
    with pytest.raises(EquationEnrichmentInventoryError, match="partial"):
        require_equation_enrichment_inventory(root)

    (root / "index.json").write_text("{}", encoding="utf-8")
    complete = require_equation_enrichment_inventory(root)
    assert complete.status is EquationEnrichmentInventoryStatus.COMPLETE_PAIR
    assert complete.problem_codes == ()


def test__enrichment_inventory__rejects_symlink_member(tmp_path: Path) -> None:
    root = tmp_path / "enrichment"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (root / "recognition.json").symlink_to(outside)
    (root / "index.json").write_text("{}", encoding="utf-8")

    inventory = inspect_equation_enrichment_inventory(root)

    assert inventory.status is EquationEnrichmentInventoryStatus.PARTIAL
    assert inventory.problem_codes == ("recognition_unsafe",)
    with pytest.raises(
        EquationEnrichmentInventoryError, match="recognition_unsafe"
    ):
        require_equation_enrichment_inventory(root)


def test__recognition_deferral__only_changes_untouched_pending_work() -> None:
    pending = defer_equation_recognition(
        EquationRecognitionCheckpoint(EquationRecognitionWorkState.PENDING)
    )
    complete = defer_equation_recognition(
        EquationRecognitionCheckpoint(EquationRecognitionWorkState.COMPLETE)
    )
    failed = defer_equation_recognition(
        EquationRecognitionCheckpoint(
            EquationRecognitionWorkState.FAILED,
            error="bounded recognizer failure",
        )
    )

    assert pending.resulting_state is EquationRecognitionWorkState.NOT_REQUESTED
    assert pending.changed is True
    assert complete.resulting_state is EquationRecognitionWorkState.COMPLETE
    assert complete.changed is False
    assert failed.resulting_state is EquationRecognitionWorkState.FAILED
    assert failed.preserved_error == "bounded recognizer failure"
    assert failed.changed is False


def test__recognition_checkpoint__requires_and_preserves_failure_evidence() -> (
    None
):
    with pytest.raises(ValueError, match="requires an error"):
        EquationRecognitionCheckpoint(EquationRecognitionWorkState.FAILED)
    with pytest.raises(ValueError, match="cannot have an error"):
        EquationRecognitionCheckpoint(
            EquationRecognitionWorkState.PENDING,
            error="must not be erased",
        )
