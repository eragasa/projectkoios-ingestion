from __future__ import annotations

import json
import stat
import sys
from pathlib import Path, PurePosixPath

import pytest
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage
from projectkoios.ingestion.ocr.batch.plan import SelectiveOCRPlan
from projectkoios.ingestion.ocr.reconciliation.batch.item import (
    SelectiveOCRReconciliationItem,
)
from projectkoios.ingestion.ocr.reconciliation.batch.page import (
    SelectiveOCRReconciliationPage,
)
from projectkoios.ingestion.ocr.reconciliation.batch.plan import (
    SelectiveOCRReconciliationPlan,
)
from projectkoios.ingestion.ocr_batch_cli import main as selective_ocr_batch
from projectkoios.ingestion.pdf.batch.item import PdfBatchItem
from projectkoios.ingestion.pdf.batch.json import PdfBatchPlanJsonContract
from projectkoios.ingestion.pdf.batch.plan import PdfBatchPlan
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.verifier import SHA256Verifier

from scripts.ocr_reconciliation_batch import main as reconcile_batch

pymupdf = pytest.importorskip("pymupdf")


def _image_only_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=148, height=72)
    page.insert_image(
        page.rect,
        stream=Path("tests/fixtures/ocr/synthetic-text.png").read_bytes(),
    )
    payload = document.tobytes()
    document.close()
    return payload


def _tesseract(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "fake-tesseract"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('tesseract 5.5.0')\n"
        "    raise SystemExit(0)\n"
        "print('level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext')\n"
        "print('5\\t1\\t1\\t1\\t1\\t1\\t10\\t10\\t40\\t15\\t42.0\\tOCR')\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    traineddata = tmp_path / "eng.traineddata"
    traineddata.write_bytes(b"synthetic traineddata identity")
    return executable, traineddata


def test__ocr_reconciliation_batch__is_dry_run_create_once_and_resumable(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    payload = _image_only_pdf()
    pdf = source_root / "fixture.pdf"
    pdf.write_bytes(payload)
    source = PdfBatchItem(
        source_id="source:reconciliation-batch-fixture",
        pdf_path=PurePosixPath("fixture.pdf"),
        output_directory=PurePosixPath("native/fixture"),
        sha256=SHA256Fingerprinter.fingerprint(content=payload),
        byte_size=len(payload),
        locator="fixture://reconciliation-batch.pdf",
    )
    native_plan_path = tmp_path / "native-plan.json"
    native_plan_path.write_text(
        PdfBatchPlanJsonContract().serialize_text(
            PdfBatchPlan(schema_version=1, items=(source,))
        ),
        encoding="utf-8",
    )
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
    ocr_item = SelectiveOCRItem(
        source=source,
        extraction_sha256=SHA256Fingerprinter.fingerprint(
            content=extraction.read_bytes()
        ),
        output_directory=PurePosixPath("ocr/fixture"),
        pages=(SelectiveOCRPage(0),),
    )
    ocr_plan_path = tmp_path / "ocr-plan.json"
    ocr_plan_path.write_text(
        SelectiveOCRPlan(schema_version=1, items=(ocr_item,)).to_json(),
        encoding="utf-8",
    )
    ocr_root = tmp_path / "ocr"
    ocr_root.mkdir(mode=0o700)
    executable, traineddata = _tesseract(tmp_path)
    assert (
        selective_ocr_batch(
            [
                str(ocr_plan_path),
                "--source-root",
                str(source_root),
                "--ingestion-root",
                str(ingestion_root),
                "--output-root",
                str(ocr_root),
                "--tesseract-executable",
                str(executable),
                "--traineddata",
                str(traineddata),
                "--apply",
            ]
        )
        == 0
    )
    json.loads(capfd.readouterr().out)
    ocr_artifact = ocr_root / "ocr/fixture/page-000001/result.json"
    reconciliation_item = SelectiveOCRReconciliationItem(
        source=source,
        extraction_sha256=ocr_item.extraction_sha256,
        ocr_directory=ocr_item.output_directory,
        output_directory=PurePosixPath("reconciliation/fixture"),
        pages=(
            SelectiveOCRReconciliationPage(
                page_index=0,
                ocr_publication_sha256=SHA256Fingerprinter.fingerprint(
                    content=ocr_artifact.read_bytes()
                ),
            ),
        ),
    )
    reconciliation_plan_path = tmp_path / "reconciliation-plan.json"
    reconciliation_plan_path.write_text(
        SelectiveOCRReconciliationPlan(
            schema_version=1,
            items=(reconciliation_item,),
        ).to_json(),
        encoding="utf-8",
    )
    output_root = tmp_path / "reconciliation"
    output_root.mkdir(mode=0o700)
    stale_plan_path = tmp_path / "stale-reconciliation-plan.json"
    stale_plan_path.write_text(
        SelectiveOCRReconciliationPlan(
            schema_version=1,
            items=(
                SelectiveOCRReconciliationItem(
                    source=source,
                    extraction_sha256=ocr_item.extraction_sha256,
                    ocr_directory=ocr_item.output_directory,
                    output_directory=PurePosixPath("reconciliation/fixture"),
                    pages=(
                        SelectiveOCRReconciliationPage(
                            page_index=0,
                            ocr_publication_sha256="e" * 64,
                        ),
                    ),
                ),
            ),
        ).to_json(),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="2"):
        reconcile_batch(
            [
                str(stale_plan_path),
                "--ingestion-root",
                str(ingestion_root),
                "--ocr-root",
                str(ocr_root),
                "--output-root",
                str(output_root),
            ]
        )
    assert "selective OCR publication SHA-256 changed" in capfd.readouterr().err

    arguments = [
        str(reconciliation_plan_path),
        "--ingestion-root",
        str(ingestion_root),
        "--ocr-root",
        str(ocr_root),
        "--output-root",
        str(output_root),
    ]

    assert reconcile_batch(arguments) == 2
    planned = json.loads(capfd.readouterr().out)
    assert planned["reconciliation_execution"] == "not_executed"
    assert planned["items"][0]["action"] == "create"

    assert reconcile_batch([*arguments, "--apply"]) == 0
    created = json.loads(capfd.readouterr().out)
    assert created["items"][0]["action"] == "created"
    assert created["items"][0]["native_item_count"] == 0
    assert created["items"][0]["ocr_item_count"] == 1
    assert created["items"][0]["artifact"] == (
        "reconciliation/fixture/page-000001/result.json"
    )
    artifact = output_root / "reconciliation/fixture/page-000001/result.json"
    assert SHA256Verifier.verify(
        content=artifact.read_bytes(),
        expected=created["items"][0]["artifact_sha256"],
    )
    before = (
        SHA256Fingerprinter.fingerprint(content=artifact.read_bytes()),
        artifact.stat().st_size,
        artifact.stat().st_mtime_ns,
    )
    assert stat.S_IMODE(artifact.stat().st_mode) == 0o600
    assert stat.S_IMODE(artifact.parent.stat().st_mode) == 0o700

    assert reconcile_batch([*arguments, "--apply"]) == 0
    replayed = json.loads(capfd.readouterr().out)
    assert replayed["items"][0]["action"] == "unchanged"
    assert (
        SHA256Fingerprinter.fingerprint(content=artifact.read_bytes()),
        artifact.stat().st_size,
        artifact.stat().st_mtime_ns,
    ) == before
