from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.equation_batch_cli import main as equation_batch

FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


def _plan(payload: bytes) -> PdfBatchPlan:
    return PdfBatchPlan(
        schema_version=1,
        items=(
            PdfBatchItem(
                source_id="article:equation:batch",
                pdf_path=PurePosixPath("equations.pdf"),
                output_directory=PurePosixPath("article"),
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_size=len(payload),
                locator="assets/equations.pdf",
            ),
        ),
    )


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    payload = (FIXTURES / "equations.pdf").read_bytes()
    source = tmp_path / "source"
    source.mkdir()
    shutil.copyfile(FIXTURES / "equations.pdf", source / "equations.pdf")
    plan = tmp_path / "plan.json"
    plan.write_text(_plan(payload).to_json(), encoding="utf-8")
    ingestion = tmp_path / "ingestion"
    assert (
        ingest_batch(
            [
                str(plan),
                "--source-root",
                str(source),
                "--output-root",
                str(ingestion),
                "--apply",
            ]
        )
        == 0
    )
    return source, plan, ingestion


def test__equation_batch__plans_then_creates_retrieval_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, plan, ingestion = _setup(tmp_path)
    capsys.readouterr()

    assert (
        equation_batch(
            [
                str(plan),
                "--source-root",
                str(source),
                "--ingestion-root",
                str(ingestion),
            ]
        )
        == 2
    )
    planned = json.loads(capsys.readouterr().out)
    assert planned["items"][0]["action"] == "create"
    assert not (ingestion / "article/derived").exists()

    assert (
        equation_batch(
            [
                str(plan),
                "--source-root",
                str(source),
                "--ingestion-root",
                str(ingestion),
                "--apply",
            ]
        )
        == 0
    )
    completed = json.loads(capsys.readouterr().out)
    item = completed["items"][0]
    assert item["action"] == "created"
    assert item["candidate_count"] == 1
    assert item["display_candidate_count"] == 1
    assert item["inline_candidate_count"] == 0
    assert item["transcription_status"] == "native_text_only"

    derived = ingestion / "article/derived/equations"
    detection = json.loads((derived / "detection.json").read_text())
    retrieval = json.loads((derived / "retrieval.json").read_text())
    assert detection["candidates"][0]["raw_text"] == "E = m c^2    (1)"
    assert retrieval["records"][0]["raw_text"] == "E = m c^2    (1)"
    assert "Preceding context" in retrieval["records"][0]["retrieval_text"]
    assert retrieval["records"][0]["transcription_status"] == (
        "native_text_only"
    )
    assert "content" not in retrieval["records"][0]


def test__equation_batch__replay_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, plan, ingestion = _setup(tmp_path)
    capsys.readouterr()
    arguments = [
        str(plan),
        "--source-root",
        str(source),
        "--ingestion-root",
        str(ingestion),
        "--apply",
    ]
    assert equation_batch(arguments) == 0
    first = json.loads(capsys.readouterr().out)
    assert equation_batch(arguments) == 0
    second = json.loads(capsys.readouterr().out)

    assert first["items"][0]["action"] == "created"
    assert second["items"][0]["action"] == "unchanged"
    assert (
        first["items"][0]["detection_artifact_sha256"]
        == second["items"][0]["detection_artifact_sha256"]
    )
    assert (
        first["items"][0]["retrieval_artifact_sha256"]
        == second["items"][0]["retrieval_artifact_sha256"]
    )


def test__equation_batch__refuses_different_existing_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, plan, ingestion = _setup(tmp_path)
    capsys.readouterr()
    arguments = [
        str(plan),
        "--source-root",
        str(source),
        "--ingestion-root",
        str(ingestion),
        "--apply",
    ]
    assert equation_batch(arguments) == 0
    capsys.readouterr()
    retrieval = ingestion / "article/derived/equations/retrieval.json"
    retrieval.write_text("{}\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        equation_batch(arguments)


def test__equation_batch__rejects_raw_extraction_identity_mismatch(
    tmp_path: Path,
) -> None:
    source, plan, ingestion = _setup(tmp_path)
    extraction = ingestion / "article/extraction.json"
    value = json.loads(extraction.read_text())
    value["document"]["source"]["content_hash"] = "0" * 64
    extraction.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        equation_batch(
            [
                str(plan),
                "--source-root",
                str(source),
                "--ingestion-root",
                str(ingestion),
            ]
        )
