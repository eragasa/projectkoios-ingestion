from pathlib import Path, PurePosixPath

from projectkoios.ingestion.batch import PdfBatchItem
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage
from projectkoios.ingestion.ocr.batch.publication import (
    SelectiveOCRPublication,
)
from projectkoios.ingestion.ocr.configuration import OCRConfiguration
from projectkoios.ingestion.ocr.language_resource_identity import (
    OCRLanguageResourceIdentity,
)
from projectkoios.ingestion.ocr.page_image import OCRPageImage
from projectkoios.ingestion.ocr.processor_identity import OCRProcessorIdentity
from projectkoios.ingestion.ocr.request import OCRRequest
from projectkoios.ingestion.ocr.resource_identity_kind import (
    OCRResourceIdentityKind,
)
from projectkoios.ingestion.ocr.result import OCRResult
from projectkoios.ingestion.ocr.selection import OCRSelection
from projectkoios.ingestion.ocr.selection_result import OCRSelectionResult
from projectkoios.ingestion.ocr.selection_status import OCRSelectionStatus
from projectkoios.ingestion.pdf.models import (
    RegionRenderConfiguration,
    RenderedRegion,
)
from projectkoios.ingestion.serialization import contract_dict


def test__selective_ocr_publication__binds_plan_and_result() -> None:
    source_content = b"%PDF-1.7\nselective OCR publication fixture\n"
    source = SourceDocument.from_bytes(
        source_content,
        source_id="source:selective-ocr-publication",
        media_type="application/pdf",
        locator="memory://selective-ocr.pdf",
    )
    region = RenderedRegion.create(
        source=source,
        page_index=0,
        printed_page_label="1",
        source_bounding_box=(0.0, 0.0, 148.0, 22.0),
        effective_source_bounding_box=(0.0, 0.0, 148.0, 22.0),
        pixel_to_source_matrix=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        page_rotation_degrees=0,
        selection_was_full_page=True,
        configuration=RegionRenderConfiguration(resolution_dpi=72),
        content=Path("tests/fixtures/ocr/synthetic-text.png").read_bytes(),
        width_pixels=148,
        height_pixels=22,
        processor_name="fixture-renderer",
        processor_version="1",
        backend_name="fixture-backend",
        backend_version="1",
    )
    selection = OCRSelection.create(OCRPageImage.from_rendered_region(region))
    configuration = OCRConfiguration(languages=("en",))
    request = OCRRequest.create((selection,), configuration=configuration)
    identity = OCRProcessorIdentity(
        processor_name="fixture-ocr",
        processor_version="1",
        backend_name="fixture-backend",
        backend_version="1",
        language_resources=(
            OCRLanguageResourceIdentity(
                language="en",
                resource_name="eng",
                identity_kind=OCRResourceIdentityKind.SHA256,
                resource_identity="c" * 64,
            ),
        ),
    )
    selection_result = OCRSelectionResult.create(
        selection=selection,
        configuration=configuration,
        status=OCRSelectionStatus.COMPLETED,
        processor_name=identity.processor_name,
        processor_version=identity.processor_version,
        backend_name=identity.backend_name,
        backend_version=identity.backend_version,
    )
    result = OCRResult.create(
        request=request,
        selection_results=(selection_result,),
        processor_identity=identity,
    )
    item = SelectiveOCRItem(
        source=PdfBatchItem(
            source_id=source.source_id,
            pdf_path=PurePosixPath("fixture.pdf"),
            output_directory=PurePosixPath("native/fixture"),
            sha256=source.content_hash,
            byte_size=source.byte_length,
        ),
        extraction_sha256="d" * 64,
        output_directory=PurePosixPath("ocr/fixture"),
        pages=(SelectiveOCRPage(0),),
    )

    publication = SelectiveOCRPublication.create(
        item=item,
        page=item.pages[0],
        result=result,
    )

    assert publication.result is result
    assert publication.source_sha256 == source.content_hash
    assert publication.extraction_sha256 == "d" * 64
    assert (
        SelectiveOCRPublication.from_dict(contract_dict(publication))
        == publication
    )
