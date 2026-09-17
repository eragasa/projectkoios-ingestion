from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion.batch_cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "pdf"
FIRST_PDF = (FIXTURES / "born-digital-text.pdf").read_bytes()
SECOND_PDF = (FIXTURES / "figures.pdf").read_bytes()


def _plan() -> PdfBatchPlan:
    return PdfBatchPlan(
        schema_version=1,
        items=(
            PdfBatchItem(
                source_id="reference:first",
                pdf_path=PurePosixPath("first.pdf"),
                output_directory=PurePosixPath("first"),
                sha256=hashlib.sha256(FIRST_PDF).hexdigest(),
                byte_size=len(FIRST_PDF),
                locator="assets/first.pdf",
            ),
            PdfBatchItem(
                source_id="reference:second",
                pdf_path=PurePosixPath("second.pdf"),
                output_directory=PurePosixPath("second"),
                sha256=hashlib.sha256(SECOND_PDF).hexdigest(),
                byte_size=len(SECOND_PDF),
            ),
        ),
    )


def test__pdf_batch_plan__round_trips_and_rejects_unsafe_paths() -> None:
    plan = _plan()

    assert PdfBatchPlan.from_json(plan.to_json()) == plan

    value = json.loads(plan.to_json())
    value["items"][0]["pdf_path"] = "../escape.pdf"
    with pytest.raises(ValueError, match="safe relative path"):
        PdfBatchPlan.from_json(json.dumps(value))


def test__pdf_batch_plan__rejects_duplicate_destinations() -> None:
    first, second = _plan().items

    with pytest.raises(ValueError, match="duplicate output_directory"):
        PdfBatchPlan(
            schema_version=1,
            items=(
                first,
                PdfBatchItem(
                    source_id=second.source_id,
                    pdf_path=second.pdf_path,
                    output_directory=first.output_directory,
                    sha256=second.sha256,
                    byte_size=second.byte_size,
                ),
            ),
        )


def test__batch_cli__plans_then_applies_without_overwriting(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    shutil.copyfile(FIXTURES / "born-digital-text.pdf", sources / "first.pdf")
    shutil.copyfile(FIXTURES / "figures.pdf", sources / "second.pdf")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_plan().to_json(), encoding="utf-8")
    output = tmp_path / "ingestion"
    cache = tmp_path / "cache"
    arguments = [
        str(plan_path),
        "--source-root",
        str(sources),
        "--output-root",
        str(output),
        "--cache-root",
        str(cache),
    ]

    assert main(arguments) == 2
    planned = json.loads(capsys.readouterr().out)
    assert planned["status"] == "planned"
    assert not output.exists()

    assert main([*arguments, "--apply"]) == 0
    completed = json.loads(capsys.readouterr().out)
    assert completed["status"] == "completed"
    assert len(completed["items"]) == 2
    assert completed["items"][0]["source_id"] == "reference:first"
    assert completed["items"][0]["page_count"] == 1
    assert completed["items"][0]["warning_count"] == 0
    assert (output / "first" / "extraction.json").is_file()
    assert (output / "first" / "pages" / "page-0001.txt").is_file()
    assert (output / "second" / "extraction.json").is_file()

    with pytest.raises(SystemExit, match="2"):
        main([*arguments, "--apply"])
    assert "refusing to overwrite" in capsys.readouterr().err


def test__batch_cli__rejects_source_changed_after_plan(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    shutil.copyfile(FIXTURES / "born-digital-text.pdf", sources / "first.pdf")
    shutil.copyfile(FIXTURES / "figures.pdf", sources / "second.pdf")
    first = sources / "first.pdf"
    payload = first.read_bytes()
    first.write_bytes(payload[:-1] + bytes((payload[-1] ^ 1,)))
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_plan().to_json(), encoding="utf-8")
    output = tmp_path / "ingestion"

    with pytest.raises(SystemExit, match="2"):
        main(
            [
                str(plan_path),
                "--source-root",
                str(sources),
                "--output-root",
                str(output),
                "--apply",
            ]
        )

    assert not output.exists()


def test__batch_cli__rejects_existing_output_symlink(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    shutil.copyfile(FIXTURES / "born-digital-text.pdf", sources / "first.pdf")
    shutil.copyfile(FIXTURES / "figures.pdf", sources / "second.pdf")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_plan().to_json(), encoding="utf-8")
    output = tmp_path / "ingestion"
    output.mkdir()
    (output / "first").symlink_to(tmp_path / "outside")

    with pytest.raises(SystemExit, match="2"):
        main(
            [
                str(plan_path),
                "--source-root",
                str(sources),
                "--output-root",
                str(output),
                "--apply",
            ]
        )

    assert not (tmp_path / "outside").exists()


def test__batch_cli__preflights_every_destination_before_mutation(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    shutil.copyfile(FIXTURES / "born-digital-text.pdf", sources / "first.pdf")
    shutil.copyfile(FIXTURES / "figures.pdf", sources / "second.pdf")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_plan().to_json(), encoding="utf-8")
    output = tmp_path / "ingestion"
    (output / "second").mkdir(parents=True)

    with pytest.raises(SystemExit, match="2"):
        main(
            [
                str(plan_path),
                "--source-root",
                str(sources),
                "--output-root",
                str(output),
                "--apply",
            ]
        )

    assert not (output / "first").exists()
