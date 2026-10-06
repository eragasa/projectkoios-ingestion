from __future__ import annotations

from pathlib import Path, PurePosixPath

from projectkoios.ingestion.batch import PdfBatchItem
from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.ocr.batch.item import SelectiveOCRItem
from projectkoios.ingestion.ocr.batch.page import SelectiveOCRPage
from projectkoios.ingestion.ocr.batch.publication import SelectiveOCRPublication
from projectkoios.ingestion.ocr.configuration import OCRConfiguration
from projectkoios.ingestion.ocr.identity.processor import OCRProcessorIdentity
from projectkoios.ingestion.ocr.identity.resource.language import (
    OCRLanguageResourceIdentity,
)
from projectkoios.ingestion.ocr.image.page import OCRPageImage
from projectkoios.ingestion.ocr.kind.resource.identity import (
    OCRResourceIdentityKind,
)
from projectkoios.ingestion.ocr.reconciliation.batch.item import (
    SelectiveOCRReconciliationItem,
)
from projectkoios.ingestion.ocr.reconciliation.batch.page import (
    SelectiveOCRReconciliationPage,
)
from projectkoios.ingestion.ocr.request import OCRRequest
from projectkoios.ingestion.ocr.result.ocr import OCRResult
from projectkoios.ingestion.ocr.result.selection import OCRSelectionResult
from projectkoios.ingestion.ocr.selection import OCRSelection
from projectkoios.ingestion.ocr.status.selection import OCRSelectionStatus
from projectkoios.ingestion.pdf.models import (
    RegionRenderConfiguration,
    RenderedRegion,
)
from projectkoios.ingestion.reconciliation.reconciler import (
    DeterministicOCRReconciler,
)
from projectkoios.ingestion.reconciliation.request import (
    OCRReconciliationRequest,
)
from projectkoios.ingestion.reconciliation.result import OCRReconciliationResult
from projectkoios.ingestion.serialization import serialize_contract
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


def reconciliation_fixture() -> tuple[
    SelectiveOCRReconciliationItem,
    SelectiveOCRReconciliationPage,
    SelectiveOCRPublication,
]:
    source_content = b"%PDF-1.7\nselective reconciliation fixture\n"
    source = SourceDocument.from_bytes(
        source_content,
        source_id="source:selective-reconciliation",
        media_type="application/pdf",
        locator="memory://selective-reconciliation.pdf",
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
        backend_name="fixture-renderer-backend",
        backend_version="1",
    )
    selection = OCRSelection.create(OCRPageImage.from_rendered_region(region))
    configuration = OCRConfiguration(languages=("en",))
    request = OCRRequest.create((selection,), configuration=configuration)
    identity = OCRProcessorIdentity(
        processor_name="fixture-ocr",
        processor_version="1",
        backend_name="fixture-ocr-backend",
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
    source_item = PdfBatchItem(
        source_id=source.source_id,
        pdf_path=PurePosixPath("fixture.pdf"),
        output_directory=PurePosixPath("native/fixture"),
        sha256=source.content_hash,
        byte_size=source.byte_length,
        locator=source.locator,
    )
    ocr_item = SelectiveOCRItem(
        source=source_item,
        extraction_sha256="d" * 64,
        output_directory=PurePosixPath("ocr/fixture"),
        pages=(SelectiveOCRPage(0),),
    )
    ocr_publication = SelectiveOCRPublication.create(
        item=ocr_item,
        page=ocr_item.pages[0],
        result=result,
    )
    ocr_digest = SHA256Fingerprinter.fingerprint(
        content=(serialize_contract(ocr_publication) + "\n").encode()
    )
    page = SelectiveOCRReconciliationPage(
        page_index=0,
        ocr_publication_sha256=ocr_digest,
    )
    item = SelectiveOCRReconciliationItem(
        source=source_item,
        extraction_sha256=ocr_item.extraction_sha256,
        ocr_directory=ocr_item.output_directory,
        output_directory=PurePosixPath("reconciliation/fixture"),
        pages=(page,),
    )
    return item, page, ocr_publication


def reconciliation_result() -> OCRReconciliationResult:
    _, _, ocr_publication = reconciliation_fixture()
    request = OCRReconciliationRequest.create(
        ocr_result=ocr_publication.result,
        selection_index=0,
    )
    return DeterministicOCRReconciler().action(request=request)
