from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from projectkoios.ingestion.transcript_batch import TranscriptBatchPlan

from tests.projectkoios.ingestion.transcript.batch.fixture import (
    TranscriptBatchFixture,
)


def test__transcript_batch_plan__rejects_invalid_serialized_contracts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = TranscriptBatchFixture.create(
        tmp_path=tmp_path,
        capture=capsys,
    )
    plan = fixture.create_plan()
    value = json.loads(plan.to_json())
    value["unknown"] = True
    with pytest.raises(ValueError, match="fields do not match"):
        TranscriptBatchPlan.from_json(json.dumps(value))

    duplicate = plan.to_json().replace(
        '"plan_id":',
        '"plan_id": "duplicate", "plan_id":',
    )
    with pytest.raises(ValueError, match="duplicate member"):
        TranscriptBatchPlan.from_json(duplicate)

    changed = json.loads(plan.to_json())
    changed["extraction_low_text_threshold"] = 41
    with pytest.raises(ValueError, match="identity is inconsistent"):
        TranscriptBatchPlan.from_json(json.dumps(changed))
    with pytest.raises(ValueError, match="malformed"):
        TranscriptBatchPlan.from_json(plan.to_json()[:-3])

    for removed_key in (
        "artifact_generation",
        "schema_version",
        "contract_version",
        "configuration_version",
    ):
        removed = json.loads(plan.to_json())
        removed[removed_key] = 1
        with pytest.raises(ValueError, match="fields do not match"):
            TranscriptBatchPlan.from_json(json.dumps(removed))

    assert not os.path.lexists(
        fixture.ingestion / "article/derived/transcription/clean.json"
    )
