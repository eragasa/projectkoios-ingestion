from __future__ import annotations

import shutil
from pathlib import Path

import projectkoios.ingestion.transcript_batch as transcript_batch_module
import pytest
from projectkoios.ingestion.transcript_batch import (
    TRANSCRIPT_OUTPUT_RELATIVE_PATH,
    TranscriptBatchPublicationError,
)
from projectkoios.ingestion.transcript_batch_cli import (
    main as transcript_batch,
)

from tests.projectkoios.ingestion.transcript.batch.fixture import (
    TranscriptBatchFixture,
)


def test__transcript_batch__different_existing_output_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = TranscriptBatchFixture.create(
        tmp_path=tmp_path,
        capture=capsys,
    )
    fixture.create_plan()
    arguments = fixture.execution_arguments()
    assert transcript_batch([*arguments, "--apply"]) == 0
    capsys.readouterr()
    target = (
        fixture.ingestion
        / "article"
        / Path(TRANSCRIPT_OUTPUT_RELATIVE_PATH)
    )
    changed = target / "clean.txt"
    changed.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        transcript_batch([*arguments, "--apply"])

    assert "existing transcript artifact differs" in capsys.readouterr().err
    assert changed.read_text(encoding="utf-8") == "tampered\n"


def test__transcript_batch__incomplete_and_symlinked_sets_fail_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = TranscriptBatchFixture.create(
        tmp_path=tmp_path,
        capture=capsys,
    )
    fixture.create_plan()
    arguments = fixture.execution_arguments()
    target = (
        fixture.ingestion
        / "article"
        / Path(TRANSCRIPT_OUTPUT_RELATIVE_PATH)
    )
    target.mkdir(parents=True)
    (target / "clean.txt").write_text("partial\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        transcript_batch(arguments)
    assert "incomplete or contains extras" in capsys.readouterr().err

    shutil.rmtree(target)
    outside = tmp_path / "outside"
    outside.mkdir()
    target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SystemExit, match="2"):
        transcript_batch(arguments)
    assert "not a safe directory" in capsys.readouterr().err
    assert not tuple(outside.iterdir())


def test__transcript_batch__publication_failure_removes_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "derived/transcription"
    calls = 0
    original = transcript_batch_module._write_staged_file

    def fail_second(path: Path, text: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected write failure")
        original(path, text)

    monkeypatch.setattr(
        transcript_batch_module,
        "_write_staged_file",
        fail_second,
    )
    files = {
        name: f"{name}\n" for name in transcript_batch_module._OUTPUT_NAMES
    }

    with pytest.raises(
        TranscriptBatchPublicationError,
        match="could not publish",
    ):
        transcript_batch_module._publish_directory(target, files)

    assert not target.exists()
    assert not tuple(target.parent.glob(".transcription.tmp-*"))
    lock = target.parent / ".transcription.publish.lock"
    assert not lock.exists()

    monkeypatch.setattr(
        transcript_batch_module,
        "_write_staged_file",
        original,
    )
    lock.write_text("active\n", encoding="utf-8")
    with pytest.raises(
        TranscriptBatchPublicationError,
        match="another transcript publication is active",
    ):
        transcript_batch_module._publish_directory(target, files)
    assert lock.read_text(encoding="utf-8") == "active\n"
