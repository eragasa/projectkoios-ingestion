from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion import (
    PdfBatchItem,
    PdfBatchPlan,
    TranscriptV2BatchPlan,
)
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.equation_batch_cli import main as equation_batch
from projectkoios.ingestion.transcript_v2_batch import (
    TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH,
    TranscriptV2BatchPublicationError,
    _publish_directory,
)
from projectkoios.ingestion.transcript_v2_batch_cli import (
    main as transcript_v2_batch,
)
from projectkoios.ingestion.transcript_v2_plan_cli import (
    main as transcript_v2_plan,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


def _setup(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> tuple[Path, Path, Path, Path]:
    payload = (FIXTURES / "equations.pdf").read_bytes()
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    shutil.copyfile(FIXTURES / "equations.pdf", source / "equations.pdf")
    source_plan = PdfBatchPlan(
        schema_version=1,
        items=(
            PdfBatchItem(
                source_id="article:transcript-v2:batch",
                pdf_path=PurePosixPath("equations.pdf"),
                output_directory=PurePosixPath("article"),
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_size=len(payload),
                locator="assets/equations.pdf",
            ),
        ),
    )
    source_plan_path = tmp_path / "source-plan.json"
    source_plan_path.write_text(source_plan.to_json(), encoding="utf-8")
    ingestion = tmp_path / "ingestion"
    assert (
        ingest_batch(
            [
                str(source_plan_path),
                "--source-root",
                str(source),
                "--output-root",
                str(ingestion),
                "--apply",
            ]
        )
        == 0
    )
    assert (
        equation_batch(
            [
                str(source_plan_path),
                "--source-root",
                str(source),
                "--ingestion-root",
                str(ingestion),
                "--apply",
            ]
        )
        == 0
    )
    capsys.readouterr()
    durable_plan = tmp_path / "plans/transcript-v2-plan.json"
    return source, source_plan_path, ingestion, durable_plan


def _plan_arguments(
    source: Path,
    source_plan: Path,
    ingestion: Path,
    durable_plan: Path,
) -> list[str]:
    return [
        str(source_plan),
        "--source-root",
        str(source),
        "--ingestion-root",
        str(ingestion),
        "--output",
        str(durable_plan),
    ]


def _batch_arguments(
    source: Path,
    ingestion: Path,
    durable_plan: Path,
) -> list[str]:
    return [
        str(durable_plan),
        "--source-root",
        str(source),
        "--ingestion-root",
        str(ingestion),
    ]


def _create_plan(
    source: Path,
    source_plan: Path,
    ingestion: Path,
    durable_plan: Path,
    capsys: pytest.CaptureFixture[str],
) -> TranscriptV2BatchPlan:
    arguments = _plan_arguments(
        source, source_plan, ingestion, durable_plan
    )
    assert transcript_v2_plan(arguments) == 2
    assert not durable_plan.exists()
    planned = json.loads(capsys.readouterr().out)
    assert planned["status"] == "planned"
    assert transcript_v2_plan([*arguments, "--apply"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["action"] == "created"
    assert oct(durable_plan.stat().st_mode & 0o777) == "0o600"
    assert oct(durable_plan.parent.stat().st_mode & 0o777) == "0o700"
    assert transcript_v2_plan([*arguments, "--apply"]) == 0
    unchanged = json.loads(capsys.readouterr().out)
    assert unchanged["action"] == "unchanged"
    plan = TranscriptV2BatchPlan.from_json(
        durable_plan.read_text(encoding="utf-8")
    )
    assert plan.plan_id == created["plan_id"]
    return plan


def test__transcript_v2_batch__plans_publishes_and_replays_immutably(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, source_plan, ingestion, durable_plan = _setup(tmp_path, capsys)
    plan = _create_plan(
        source,
        source_plan,
        ingestion,
        durable_plan,
        capsys,
    )
    arguments = _batch_arguments(source, ingestion, durable_plan)

    assert transcript_v2_batch(arguments) == 2
    planned = json.loads(capsys.readouterr().out)
    assert planned["artifact_generation"] == 2
    assert planned["items"][0]["action"] == "create"

    assert transcript_v2_batch([*arguments, "--apply"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["items"][0]["action"] == "created"
    assert first["items"][0]["audit_status"] == "passed"
    target = ingestion / "article" / Path(
        TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH
    )
    assert {path.name for path in target.iterdir()} == {
        "audit.json",
        "clean.json",
        "clean.txt",
        "manifest.json",
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
    assert manifest["artifact_generation"] == 2
    assert manifest["status"] == "automated_unreviewed"
    assert clean["artifact_generation"] == 2
    assert clean["status"] == "automated_unreviewed"
    assert (
        dict(audit["audited_layer_counts"])[
            "clean_transcript_v2_artifacts"
        ]
        == "1"
    )
    assert audit["status"] == "passed"
    assert not (ingestion / "article/derived/transcription/clean.json").exists()
    first_bytes = {
        path.name: path.read_bytes() for path in target.iterdir()
    }

    assert transcript_v2_batch([*arguments, "--apply"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["items"][0]["action"] == "unchanged"
    assert {
        path.name: path.read_bytes() for path in target.iterdir()
    } == first_bytes


def test__transcript_v2_batch__different_existing_output_fails_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, source_plan, ingestion, durable_plan = _setup(tmp_path, capsys)
    _create_plan(source, source_plan, ingestion, durable_plan, capsys)
    arguments = _batch_arguments(source, ingestion, durable_plan)
    assert transcript_v2_batch([*arguments, "--apply"]) == 0
    capsys.readouterr()
    target = ingestion / "article" / Path(
        TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH
    )
    changed = target / "clean.txt"
    changed.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        transcript_v2_batch([*arguments, "--apply"])

    assert "existing transcript-v2 artifact differs" in capsys.readouterr().err
    assert changed.read_text(encoding="utf-8") == "tampered\n"


def test__transcript_v2_batch__incomplete_and_symlinked_sets_fail_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, source_plan, ingestion, durable_plan = _setup(tmp_path, capsys)
    _create_plan(source, source_plan, ingestion, durable_plan, capsys)
    arguments = _batch_arguments(source, ingestion, durable_plan)
    target = ingestion / "article" / Path(
        TRANSCRIPT_V2_OUTPUT_RELATIVE_PATH
    )
    target.mkdir(parents=True)
    (target / "clean.txt").write_text("partial\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        transcript_v2_batch(arguments)
    assert "incomplete or contains extras" in capsys.readouterr().err

    shutil.rmtree(target)
    outside = tmp_path / "outside"
    outside.mkdir()
    target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SystemExit, match="2"):
        transcript_v2_batch(arguments)
    assert "not a safe directory" in capsys.readouterr().err
    assert not tuple(outside.iterdir())


def test__transcript_v2_batch__predecessor_change_invalidates_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, source_plan, ingestion, durable_plan = _setup(tmp_path, capsys)
    _create_plan(source, source_plan, ingestion, durable_plan, capsys)
    detection = ingestion / "article/derived/equations/detection.json"
    original = detection.read_bytes()
    detection.write_bytes(original + b" ")

    with pytest.raises(SystemExit, match="2"):
        transcript_v2_batch(
            _batch_arguments(source, ingestion, durable_plan)
        )

    assert "differs from the durable plan" in capsys.readouterr().err
    assert detection.read_bytes() == original + b" "


def test__transcript_v2_batch__rejects_symlinked_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, source_plan, ingestion, durable_plan = _setup(tmp_path, capsys)
    original_pdf = source / "equations-original.pdf"
    (source / "equations.pdf").rename(original_pdf)
    (source / "equations.pdf").symlink_to(original_pdf)

    with pytest.raises(SystemExit, match="2"):
        transcript_v2_plan(
            _plan_arguments(
                source,
                source_plan,
                ingestion,
                durable_plan,
            )
        )
    assert "cannot traverse a symlink" in capsys.readouterr().err

    (source / "equations.pdf").unlink()
    original_pdf.rename(source / "equations.pdf")
    _create_plan(source, source_plan, ingestion, durable_plan, capsys)
    real_plan = tmp_path / "real-plan.json"
    durable_plan.rename(real_plan)
    durable_plan.symlink_to(real_plan)
    with pytest.raises(SystemExit, match="2"):
        transcript_v2_batch(
            _batch_arguments(source, ingestion, durable_plan)
        )
    assert "safe regular file" in capsys.readouterr().err


def test__transcript_v2_batch__publication_failure_removes_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from projectkoios.ingestion import transcript_v2_batch as module

    target = tmp_path / "derived/transcription/generation-2"
    calls = 0
    original = module._write_staged_file

    def fail_second(path: Path, text: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected write failure")
        original(path, text)

    monkeypatch.setattr(module, "_write_staged_file", fail_second)
    files = {name: f"{name}\n" for name in module._OUTPUT_NAMES}

    with pytest.raises(
        TranscriptV2BatchPublicationError,
        match="could not publish",
    ):
        _publish_directory(target, files)

    assert not target.exists()
    assert not tuple(target.parent.glob(".generation-2.tmp-*"))
    lock = target.parent / ".generation-2.publish.lock"
    assert not lock.exists()

    monkeypatch.setattr(module, "_write_staged_file", original)
    lock.write_text("active\n", encoding="utf-8")
    with pytest.raises(
        TranscriptV2BatchPublicationError,
        match="another transcript-v2 publication is active",
    ):
        _publish_directory(target, files)
    assert lock.read_text(encoding="utf-8") == "active\n"


def test__transcript_v2_batch__plan_rejects_unknown_and_duplicate_fields(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, source_plan, ingestion, durable_plan = _setup(tmp_path, capsys)
    plan = _create_plan(
        source,
        source_plan,
        ingestion,
        durable_plan,
        capsys,
    )
    value = json.loads(plan.to_json())
    value["unknown"] = True
    with pytest.raises(ValueError, match="fields do not match"):
        TranscriptV2BatchPlan.from_json(json.dumps(value))

    duplicate = plan.to_json().replace(
        '"schema_version": 1',
        '"schema_version": 1, "schema_version": 1',
    )
    with pytest.raises(ValueError, match="duplicate member"):
        TranscriptV2BatchPlan.from_json(duplicate)

    changed = json.loads(plan.to_json())
    changed["extraction_low_text_threshold"] = 41
    with pytest.raises(ValueError, match="identity is inconsistent"):
        TranscriptV2BatchPlan.from_json(json.dumps(changed))
    with pytest.raises(ValueError, match="malformed"):
        TranscriptV2BatchPlan.from_json(plan.to_json()[:-3])

    assert not os.path.lexists(
        ingestion / "article/derived/transcription/clean.json"
    )
