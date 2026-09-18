from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion import (
    PdfBatchItem,
    PdfBatchPlan,
    parse_reference_evidence,
    verify_reference_evidence,
)
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.equation_batch_cli import main as equation_batch
from projectkoios.ingestion.transcript_batch_cli import main as transcript_batch

FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    payload = (FIXTURES / "equations.pdf").read_bytes()
    source = tmp_path / "source"
    source.mkdir()
    shutil.copyfile(FIXTURES / "equations.pdf", source / "equations.pdf")
    plan = PdfBatchPlan(
        schema_version=1,
        items=(
            PdfBatchItem(
                source_id="article:transcript:batch",
                pdf_path=PurePosixPath("equations.pdf"),
                output_directory=PurePosixPath("article"),
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_size=len(payload),
                locator="assets/equations.pdf",
            ),
        ),
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")
    ingestion = tmp_path / "ingestion"
    assert (
        ingest_batch(
            [
                str(plan_path),
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
                str(plan_path),
                "--source-root",
                str(source),
                "--ingestion-root",
                str(ingestion),
                "--apply",
            ]
        )
        == 0
    )
    return source, plan_path, ingestion


def _arguments(source: Path, plan: Path, ingestion: Path) -> list[str]:
    return [
        str(plan),
        "--source-root",
        str(source),
        "--ingestion-root",
        str(ingestion),
    ]


def test__transcript_batch__plans_and_materializes_audited_projection(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, plan, ingestion = _setup(tmp_path)
    capsys.readouterr()
    arguments = _arguments(source, plan, ingestion)

    assert transcript_batch(arguments) == 2
    planned = json.loads(capsys.readouterr().out)
    assert planned["transcript_batch_manifest_schema_version"] == 2
    assert planned["items"][0]["action"] == "create"

    assert transcript_batch([*arguments, "--apply"]) == 0
    completed = json.loads(capsys.readouterr().out)
    item = completed["items"][0]
    assert completed["transcript_batch_manifest_schema_version"] == 2
    assert item["transcript_batch_manifest_schema_version"] == 2
    assert item["action"] == "created"
    assert item["audit_status"] == "passed"
    assert item["counts"]["source_pages"] == 1
    assert item["counts"]["equation_candidates"] == 1

    derived = ingestion / "article/derived/transcription"
    assert {path.name for path in derived.iterdir()} == {
        "audit.json",
        "clean.json",
        "clean.txt",
        "manifest.json",
        "reference-evidence.json",
    }
    clean = json.loads((derived / "clean.json").read_text())
    manifest = json.loads((derived / "manifest.json").read_text())
    audit = json.loads((derived / "audit.json").read_text())
    evidence_bytes = (derived / "reference-evidence.json").read_bytes()
    evidence = parse_reference_evidence(evidence_bytes)
    text = (derived / "clean.txt").read_text()
    assert clean["status"] == "automated_unreviewed"
    assert clean["text"] == text
    assert "E = m c^2" in text
    assert clean["blocks"][0]["raw_text"]
    assert clean["blocks"][0]["source_spans"]
    assert manifest["schema_version"] == 2
    assert manifest["status"] == "automated_unreviewed"
    assert manifest["intermediate_policy"] == (
        "deterministically_reconstructible_not_materialized"
    )
    assert audit["status"] == "passed"
    assert (
        dict(audit["audited_layer_counts"])["clean_transcript_artifacts"] == "1"
    )
    assert clean["artifact_id"] in audit["audited_artifact_ids"]
    assert not audit["findings"]
    assert item["reference_evidence_record_id"] == evidence.record_id
    assert manifest["reference_evidence_record_id"] == evidence.record_id
    assert evidence.source.content_sha256 == manifest["source_sha256"]
    assert evidence.source.byte_length == manifest["source_byte_size"]
    assert evidence.transcript.artifact_id == clean["artifact_id"]
    assert evidence.derivation_audit.report_id == audit["report_id"]
    assert evidence.derivation_audit.independently_revalidated is False
    verify_reference_evidence(
        evidence,
        source_sha256=manifest["source_sha256"],
        source_byte_length=manifest["source_byte_size"],
        source_media_type="application/pdf",
        extraction_artifact=(
            ingestion / "article/extraction.json"
        ).read_bytes(),
        clean_transcript_artifact=(derived / "clean.json").read_bytes(),
        derivation_audit_artifact=(derived / "audit.json").read_bytes(),
    )
    assert b"assets/equations.pdf" not in evidence_bytes
    assert b"derived/transcription" not in evidence_bytes


def test__transcript_batch__preserves_legacy_schema_one_set(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, plan, ingestion = _setup(tmp_path)
    capsys.readouterr()
    target = ingestion / "article/derived/transcription"
    target.mkdir()
    legacy_payloads = {
        "clean.json": b'{"legacy":"clean"}\n',
        "clean.txt": b"legacy clean text\n",
        "audit.json": b'{"legacy":"audit"}\n',
        "manifest.json": b'{"schema_version":1}\n',
    }
    for name, payload in legacy_payloads.items():
        (target / name).write_bytes(payload)

    with pytest.raises(SystemExit, match="2"):
        transcript_batch([*_arguments(source, plan, ingestion), "--apply"])

    assert "transcription artifact set is incomplete" in capsys.readouterr().err
    assert not (target / "reference-evidence.json").exists()
    assert {
        name: (target / name).read_bytes() for name in legacy_payloads
    } == legacy_payloads


def test__transcript_batch__replay_is_immutable_and_tampering_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, plan, ingestion = _setup(tmp_path)
    capsys.readouterr()
    arguments = [*_arguments(source, plan, ingestion), "--apply"]

    assert transcript_batch(arguments) == 0
    first = json.loads(capsys.readouterr().out)
    assert transcript_batch(arguments) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["items"][0]["action"] == "created"
    assert second["items"][0]["action"] == "unchanged"
    assert first["items"][0]["manifest_id"] == second["items"][0]["manifest_id"]

    clean_text = ingestion / "article/derived/transcription/clean.txt"
    clean_text.write_text("changed\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        transcript_batch(arguments)
