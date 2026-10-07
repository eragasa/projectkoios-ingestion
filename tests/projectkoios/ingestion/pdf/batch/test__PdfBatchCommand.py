from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from projectkoios.ingestion.batch_cli import main

from tests.projectkoios.ingestion.pdf.batch.fixture import PdfBatchFixture

FIXTURE = PdfBatchFixture()


def test__pdf_batch_command__plans_then_applies_without_overwriting(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sources = tmp_path / "sources"
    FIXTURE.write_sources(sources)
    plan_path = tmp_path / "plan.json"
    FIXTURE.write_plan(plan_path)
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


def test__pdf_batch_command__rejects_source_changed_after_plan(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    FIXTURE.write_sources(sources)
    first = sources / "first.pdf"
    payload = first.read_bytes()
    first.write_bytes(payload[:-1] + bytes((payload[-1] ^ 1,)))
    plan_path = tmp_path / "plan.json"
    FIXTURE.write_plan(plan_path)
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


def test__pdf_batch_command__rejects_symlinked_source(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    shutil.copyfile(
        FIXTURE.fixture_directory / "born-digital-text.pdf",
        sources / "first-real.pdf",
    )
    (sources / "first.pdf").symlink_to(sources / "first-real.pdf")
    shutil.copyfile(
        FIXTURE.fixture_directory / "figures.pdf",
        sources / "second.pdf",
    )
    plan_path = tmp_path / "plan.json"
    FIXTURE.write_plan(plan_path)
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


def test__pdf_batch_command__rejects_existing_output_symlink(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    FIXTURE.write_sources(sources)
    plan_path = tmp_path / "plan.json"
    FIXTURE.write_plan(plan_path)
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


def test__pdf_batch_command__preflights_all_targets_before_mutation(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    FIXTURE.write_sources(sources)
    plan_path = tmp_path / "plan.json"
    FIXTURE.write_plan(plan_path)
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
