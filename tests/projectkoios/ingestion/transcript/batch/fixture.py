from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import ClassVar

import pytest
from projectkoios.ingestion.batch_cli import main as ingest_batch
from projectkoios.ingestion.equation_batch_cli import main as equation_batch
from projectkoios.ingestion.pdf.batch.item import PdfBatchItem
from projectkoios.ingestion.pdf.batch.json import PdfBatchPlanJsonContract
from projectkoios.ingestion.pdf.batch.plan import PdfBatchPlan
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.transcript_batch import TranscriptBatchPlan
from projectkoios.ingestion.transcript_plan_cli import main as transcript_plan


@dataclass(frozen=True)
class TranscriptBatchFixture:
    """Own one prepared transcript-batch command scenario."""

    fixture_root: ClassVar[Path] = Path(__file__).parents[4] / "fixtures/pdf"

    source: Path
    source_plan: Path
    ingestion: Path
    durable_plan: Path
    capture: pytest.CaptureFixture[str]

    @classmethod
    def create(
        cls,
        *,
        tmp_path: Path,
        capture: pytest.CaptureFixture[str],
    ) -> TranscriptBatchFixture:
        payload = (cls.fixture_root / "equations.pdf").read_bytes()
        source = tmp_path / "source"
        source.mkdir(mode=0o700)
        shutil.copyfile(
            cls.fixture_root / "equations.pdf",
            source / "equations.pdf",
        )
        source_plan = PdfBatchPlan(
            schema_version=1,
            items=(
                PdfBatchItem(
                    source_id="article:transcript:batch",
                    pdf_path=PurePosixPath("equations.pdf"),
                    output_directory=PurePosixPath("article"),
                    sha256=SHA256Fingerprinter.fingerprint(content=payload),
                    byte_size=len(payload),
                    locator="assets/equations.pdf",
                ),
            ),
        )
        source_plan_path = tmp_path / "source-plan.json"
        source_plan_path.write_text(
            PdfBatchPlanJsonContract().serialize_text(source_plan),
            encoding="utf-8",
        )
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
        capture.readouterr()
        return cls(
            source=source,
            source_plan=source_plan_path,
            ingestion=ingestion,
            durable_plan=tmp_path / "plans/transcript-plan.json",
            capture=capture,
        )

    def plan_arguments(self) -> list[str]:
        return [
            str(self.source_plan),
            "--source-root",
            str(self.source),
            "--ingestion-root",
            str(self.ingestion),
            "--output",
            str(self.durable_plan),
        ]

    def execution_arguments(self) -> list[str]:
        return [
            str(self.durable_plan),
            "--source-root",
            str(self.source),
            "--ingestion-root",
            str(self.ingestion),
        ]

    def create_plan(self) -> TranscriptBatchPlan:
        arguments = self.plan_arguments()
        assert transcript_plan(arguments) == 2
        assert not self.durable_plan.exists()
        planned = json.loads(self.capture.readouterr().out)
        assert planned["status"] == "planned"
        assert transcript_plan([*arguments, "--apply"]) == 0
        created = json.loads(self.capture.readouterr().out)
        assert created["action"] == "created"
        assert oct(self.durable_plan.stat().st_mode & 0o777) == "0o600"
        assert oct(self.durable_plan.parent.stat().st_mode & 0o777) == "0o700"
        assert transcript_plan([*arguments, "--apply"]) == 0
        unchanged = json.loads(self.capture.readouterr().out)
        assert unchanged["action"] == "unchanged"
        plan = TranscriptBatchPlan.from_json(
            self.durable_plan.read_text(encoding="utf-8")
        )
        assert plan.plan_id == created["plan_id"]
        return plan
