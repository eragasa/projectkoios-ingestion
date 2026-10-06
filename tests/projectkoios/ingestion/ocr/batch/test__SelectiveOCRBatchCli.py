from __future__ import annotations

import json
import stat
import sys
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion import ocr_batch_cli
from projectkoios.ingestion.batch import PdfBatchItem, PdfBatchPlan
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage
from projectkoios.ingestion.ocr.batch.plan import SelectiveOCRPlan
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

pymupdf = pytest.importorskip("pymupdf")
selective_ocr_batch = ocr_batch_cli.main
_MUPDF_DIAGNOSTIC = "MuPDF error: syntax error: invalid key in dict\n"


def _pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=144, height=72)
    page.insert_text((12, 24), "native text")
    payload = document.tobytes()
    document.close()
    return payload


def _tesseract(tmp_path: Path, marker: Path) -> Path:
    executable = tmp_path / "fake-tesseract"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('tesseract 5.5.0')\n"
        "    raise SystemExit(0)\n"
        f"pathlib.Path({str(marker)!r}).open('a').write('ocr\\n')\n"
        "print('level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext')\n"
        "print('5\\t1\\t1\\t1\\t1\\t1\\t10\\t10\\t40\\t15\\t95.0\\tOCR')\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def test__selective_ocr_batch__is_dry_run_create_once_and_resumable(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    payload = _pdf()
    pdf = source_root / "fixture.pdf"
    pdf.write_bytes(payload)
    source = PdfBatchItem(
        source_id="source:selective-ocr-fixture",
        pdf_path=PurePosixPath("fixture.pdf"),
        output_directory=PurePosixPath("native/fixture"),
        sha256=SHA256Fingerprinter.fingerprint(content=payload),
        byte_size=len(payload),
        locator="fixture://selective-ocr.pdf",
    )
    native_plan = PdfBatchPlan(schema_version=1, items=(source,))
    native_plan_path = tmp_path / "native-plan.json"
    native_plan_path.write_text(native_plan.to_json(), encoding="utf-8")
    ingestion_root = tmp_path / "ingestion"
    assert (
        ingest_batch(
            [
                str(native_plan_path),
                "--source-root",
                str(source_root),
                "--output-root",
                str(ingestion_root),
                "--apply",
            ]
        )
        == 0
    )
    capfd.readouterr()
    extraction = ingestion_root / "native/fixture/extraction.json"
    ocr_plan = SelectiveOCRPlan(
        schema_version=1,
        items=(
            SelectiveOCRItem(
                source=source,
                extraction_sha256=SHA256Fingerprinter.fingerprint(
                    content=extraction.read_bytes()
                ),
                output_directory=PurePosixPath("ocr/fixture"),
                pages=(SelectiveOCRPage(0),),
            ),
        ),
    )
    ocr_plan_path = tmp_path / "ocr-plan.json"
    ocr_plan_path.write_text(ocr_plan.to_json(), encoding="utf-8")
    output_root = tmp_path / "ocr-output"
    output_root.mkdir(mode=0o700)
    output_root.chmod(0o700)
    marker = tmp_path / "ocr-invocations"
    executable = _tesseract(tmp_path, marker)
    traineddata = tmp_path / "eng.traineddata"
    traineddata.write_bytes(b"synthetic traineddata identity")
    arguments = [
        str(ocr_plan_path),
        "--source-root",
        str(source_root),
        "--ingestion-root",
        str(ingestion_root),
        "--output-root",
        str(output_root),
        "--tesseract-executable",
        str(executable),
        "--traineddata",
        str(traineddata),
    ]

    assert selective_ocr_batch(arguments) == 2
    planned_capture = capfd.readouterr()
    planned = json.loads(planned_capture.out)
    assert planned_capture.err == ""
    assert planned["ocr_execution"] == "not_executed"
    assert planned["items"][0]["action"] == "create"
    assert not marker.exists()

    extract_pdf_evidence = ocr_batch_cli.extract_pdf_evidence

    def extract_with_mupdf_diagnostic(*args: object, **kwargs: object):
        pymupdf.message(_MUPDF_DIAGNOSTIC.rstrip("\n"))
        return extract_pdf_evidence(*args, **kwargs)

    monkeypatch.setattr(
        ocr_batch_cli,
        "extract_pdf_evidence",
        extract_with_mupdf_diagnostic,
    )
    assert selective_ocr_batch([*arguments, "--apply"]) == 0
    created_capture = capfd.readouterr()
    created = json.loads(created_capture.out)
    assert created_capture.err == _MUPDF_DIAGNOSTIC
    assert created["items"][0]["action"] == "created"
    assert created["items"][0]["native_text_preserved_separately"] is True
    assert marker.read_text(encoding="utf-8") == "ocr\n"
    artifact = output_root / "ocr/fixture/page-000001/result.json"
    artifact_text = artifact.read_text(encoding="utf-8")
    assert stat.S_IMODE(artifact.stat().st_mode) == 0o600
    assert stat.S_IMODE(artifact.parent.stat().st_mode) == 0o700
    result = json.loads(artifact_text)
    assert result["result"]["request"]["selections"][0]["native_text_blocks"]
    assert result["result"]["selection_results"][0]["lines"][0]["text"] == "OCR"

    result["result"]["request"]["request_id"] = "ocr-request:changed"
    artifact.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        selective_ocr_batch([*arguments, "--apply"])
    failed_capture = capfd.readouterr()
    assert _MUPDF_DIAGNOSTIC in failed_capture.err
    assert "existing selective OCR result is inconsistent" in (
        failed_capture.err
    )
    assert failed_capture.out == ""
    artifact.write_text(artifact_text, encoding="utf-8")

    assert selective_ocr_batch([*arguments, "--apply"]) == 0
    replay_capture = capfd.readouterr()
    replayed = json.loads(replay_capture.out)
    assert replay_capture.err == _MUPDF_DIAGNOSTIC
    assert replayed["items"][0]["action"] == "unchanged"
    assert marker.read_text(encoding="utf-8") == "ocr\n"
