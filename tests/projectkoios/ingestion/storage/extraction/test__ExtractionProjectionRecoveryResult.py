from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.storage.extraction.recovery.result import (
    ExtractionProjectionRecoveryResult,
)


def test__extraction_projection_recovery_result__retains_position() -> None:
    result = ExtractionProjectionRecoveryResult(
        request_id="recovery:one",
        observed_records=2,
        projected_records=2,
        last_journal_sequence=2,
    )

    assert isinstance(result, DataObjectActionResult)
    assert result.last_journal_sequence == 2
