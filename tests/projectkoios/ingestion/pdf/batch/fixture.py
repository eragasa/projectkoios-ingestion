from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from projectkoios.ingestion.pdf.batch.item import PdfBatchItem
from projectkoios.ingestion.pdf.batch.json import PdfBatchPlanJsonContract
from projectkoios.ingestion.pdf.batch.plan import PdfBatchPlan
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True)
class PdfBatchFixture:
    """Own representative PDF payloads and plan construction."""

    fixture_directory: Path = Path(__file__).parents[4] / "fixtures" / "pdf"

    @property
    def first_payload(self) -> bytes:
        return (self.fixture_directory / "born-digital-text.pdf").read_bytes()

    @property
    def second_payload(self) -> bytes:
        return (self.fixture_directory / "figures.pdf").read_bytes()

    def item(self, index: int = 1) -> PdfBatchItem:
        payload = f"payload-{index}".encode()
        return PdfBatchItem(
            source_id=f"reference:{index}",
            pdf_path=PurePosixPath(f"source-{index}.pdf"),
            output_directory=PurePosixPath(f"source-{index}"),
            sha256=SHA256Fingerprinter.fingerprint(content=payload),
            byte_size=len(payload),
            locator=f"assets/source-{index}.pdf",
        )

    def plan(self) -> PdfBatchPlan:
        return PdfBatchPlan(
            schema_version=1,
            items=(
                PdfBatchItem(
                    source_id="reference:first",
                    pdf_path=PurePosixPath("first.pdf"),
                    output_directory=PurePosixPath("first"),
                    sha256=SHA256Fingerprinter.fingerprint(
                        content=self.first_payload
                    ),
                    byte_size=len(self.first_payload),
                    locator="assets/first.pdf",
                ),
                PdfBatchItem(
                    source_id="reference:second",
                    pdf_path=PurePosixPath("second.pdf"),
                    output_directory=PurePosixPath("second"),
                    sha256=SHA256Fingerprinter.fingerprint(
                        content=self.second_payload
                    ),
                    byte_size=len(self.second_payload),
                ),
            ),
        )

    def write_sources(self, root: Path) -> None:
        root.mkdir()
        shutil.copyfile(
            self.fixture_directory / "born-digital-text.pdf",
            root / "first.pdf",
        )
        shutil.copyfile(
            self.fixture_directory / "figures.pdf",
            root / "second.pdf",
        )

    def write_plan(self, path: Path) -> None:
        path.write_bytes(
            PdfBatchPlanJsonContract().serialize_bytes(self.plan())
        )
