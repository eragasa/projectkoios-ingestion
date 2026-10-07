from __future__ import annotations

import json
from pathlib import Path

import pytest
from projectkoios.ingestion.transcript_batch import (
    TRANSCRIPT_OUTPUT_RELATIVE_PATH,
)
from projectkoios.ingestion.transcript_batch_cli import (
    main as transcript_batch,
)
from projectkoios.ingestion.transcript_plan_cli import (
    main as transcript_plan,
)

from tests.projectkoios.ingestion.transcript.batch.fixture import (
    TranscriptBatchFixture,
)


def test__transcript_batch__plans_publishes_and_replays_immutably(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = TranscriptBatchFixture.create(
        tmp_path=tmp_path,
        capture=capsys,
    )
    plan = fixture.create_plan()
    arguments = fixture.execution_arguments()

    assert transcript_batch(arguments) == 2
    planned = json.loads(capsys.readouterr().out)
    assert planned["items"][0]["action"] == "create"

    assert transcript_batch([*arguments, "--apply"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["items"][0]["action"] == "created"
    assert first["items"][0]["audit_status"] == "passed"
    target = (
        fixture.ingestion
        / "article"
        / Path(TRANSCRIPT_OUTPUT_RELATIVE_PATH)
    )
    assert {path.name for path in target.iterdir()} == {
        "audit.json",
        "clean.json",
        "clean.txt",
        "manifest.json",
        "reference-evidence.json",
    }
    assert oct(target.stat().st_mode & 0o777) == "0o700"
    assert all(
        oct(path.stat().st_mode & 0o777) == "0o600"
        for path in target.iterdir()
    )
    manifest = json.loads((target / "manifest.json").read_text())
    clean = json.loads((target / "clean.json").read_text())
    audit = json.loads((target / "audit.json").read_text())
    assert manifest["plan_id"] == plan.plan_id
    assert manifest["status"] == "automated_unreviewed"
    assert clean["status"] == "automated_unreviewed"
    assert dict(audit["audited_layer_counts"])["clean_transcripts"] == "1"
    assert audit["status"] == "passed"
    first_bytes = {
        path.name: path.read_bytes() for path in target.iterdir()
    }

    assert transcript_batch([*arguments, "--apply"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["items"][0]["action"] == "unchanged"
    assert {
        path.name: path.read_bytes() for path in target.iterdir()
    } == first_bytes


def test__transcript_batch__predecessor_change_invalidates_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = TranscriptBatchFixture.create(
        tmp_path=tmp_path,
        capture=capsys,
    )
    fixture.create_plan()
    detection = (
        fixture.ingestion / "article/derived/equations/detection.json"
    )
    original = detection.read_bytes()
    detection.write_bytes(original + b" ")

    with pytest.raises(SystemExit, match="2"):
        transcript_batch(fixture.execution_arguments())

    assert "differs from the durable plan" in capsys.readouterr().err
    assert detection.read_bytes() == original + b" "


def test__transcript_batch__rejects_symlinked_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = TranscriptBatchFixture.create(
        tmp_path=tmp_path,
        capture=capsys,
    )
    original_pdf = fixture.source / "equations-original.pdf"
    (fixture.source / "equations.pdf").rename(original_pdf)
    (fixture.source / "equations.pdf").symlink_to(original_pdf)

    with pytest.raises(SystemExit, match="2"):
        transcript_plan(fixture.plan_arguments())
    assert "cannot traverse a symlink" in capsys.readouterr().err

    (fixture.source / "equations.pdf").unlink()
    original_pdf.rename(fixture.source / "equations.pdf")
    fixture.create_plan()
    real_plan = tmp_path / "real-plan.json"
    fixture.durable_plan.rename(real_plan)
    fixture.durable_plan.symlink_to(real_plan)
    with pytest.raises(SystemExit, match="2"):
        transcript_batch(fixture.execution_arguments())
    assert "safe regular file" in capsys.readouterr().err
