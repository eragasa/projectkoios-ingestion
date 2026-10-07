from pathlib import PurePosixPath

from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage
from projectkoios.ingestion.ocr.batch.plan import SelectiveOCRPlan
from projectkoios.ingestion.pdf.batch.item import PdfBatchItem


def test__selective_ocr_plan__round_trips_exact_json() -> None:
    plan = SelectiveOCRPlan(
        schema_version=1,
        items=(
            SelectiveOCRItem(
                source=PdfBatchItem(
                    source_id="source:fixture",
                    pdf_path=PurePosixPath("fixture.pdf"),
                    output_directory=PurePosixPath("native/fixture"),
                    sha256="a" * 64,
                    byte_size=100,
                    locator="fixture://pdf",
                ),
                extraction_sha256="b" * 64,
                output_directory=PurePosixPath("ocr/fixture"),
                pages=(SelectiveOCRPage(0), SelectiveOCRPage(2)),
            ),
        ),
    )

    assert SelectiveOCRPlan.from_json(plan.to_json()) == plan
