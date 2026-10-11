"""Fixed native-PDF current-schema production for durable publication."""

from __future__ import annotations

from io import BytesIO

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.artifact.managed.verification.result import (
    ManagedArtifactVerificationResult,
)
from projectkoios.ingestion.models import (
    ExtractionResult,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.page.projection.actionizer import (
    PageProjectionActionizer,
)
from projectkoios.ingestion.page.projection.enrichment.actionizer import (
    PageProjectionEvidenceEnrichmentActionizer,
)
from projectkoios.ingestion.page.projection.enrichment.request import (
    PageProjectionEvidenceEnrichmentRequest,
)
from projectkoios.ingestion.page.projection.publication.code import (
    PageProjectionPublicationCodeInventory,
)
from projectkoios.ingestion.page.projection.publication.configuration import (
    PageProjectionPublicationConfiguration,
)
from projectkoios.ingestion.page.projection.publication.evidence import (
    PageProjectionPublicationEvidence,
)
from projectkoios.ingestion.page.projection.request import PageProjectionRequest
from projectkoios.ingestion.pdf.adapters.pymupdf.extraction import (
    PyMuPdfExtractor,
)
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.source import (  # noqa: E501
    ReadingTextBlockSourceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.document import (
    ReadingDocumentProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.inventory import (  # noqa: E501
    ReadingEquationProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.inventory import (  # noqa: E501
    ReadingPageTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.inventory import (  # noqa: E501
    ReadingStructuredItemProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.source import (  # noqa: E501
    ReadingSourceBlockIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.inventory import (  # noqa: E501
    ReadingCleanTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.inventory import (  # noqa: E501
    ReadingTextTransformationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.expected import (  # noqa: E501
    ExpectedReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.measures import (  # noqa: E501
    ReadingEvidenceInventoryMeasures,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.affected import (  # noqa: E501
    ReadingAffectedEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.code import (
    ReadingEvidenceLimitationCode,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.definition import (  # noqa: E501
    ReadingEvidenceLimitation,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.lineage.definition import (  # noqa: E501
    ReadingEvidenceLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.actionizer import (  # noqa: E501
    ReadingEvidenceProjectionActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceProjectionConfiguration,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.request import (  # noqa: E501
    ReadingEvidenceProjectionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.result import (  # noqa: E501
    ReadingEvidenceProjectionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)
from projectkoios.ingestion.transcript.reading.evidence.span.evidence import (
    ReadingSourceSpanEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.span.geometry import (
    ReadingBoundingBox,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.evidence import (
    ReadingTextStreamEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.basis import (  # noqa: E501
    ReadingTextSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.definition import (  # noqa: E501
    ReadingTextSelection,
)


def derive_native_pdf_publication_evidence(
    *,
    content: bytes,
    source_artifact: ManagedArtifactReference,
    artifact_verification: ManagedArtifactVerificationResult,
    configuration: PageProjectionPublicationConfiguration,
    pipeline_configuration_id: str,
    maximum_page_count: int,
    maximum_block_count: int,
) -> PageProjectionPublicationEvidence:
    """Derive verification-bound source, A, and B evidence from exact bytes."""
    source_id = ReadingEvidenceIdentityDerivation.derive(
        kind=ReadingEvidenceIdentityKind.SOURCE,
        prefix="reading-managed-artifact-source",
        material={"source_artifact_id": source_artifact.artifact_id},
    )
    source = SourceDocument.from_bytes(
        content,
        source_id=source_id.value,
        media_type=source_artifact.media_type.value,
        locator=f"managed-artifact:{source_artifact.artifact_id}",
    )
    extractor = PyMuPdfExtractor(
        low_text_character_threshold=(
            configuration.low_text_character_threshold
        ),
        maximum_pages=configuration.maximum_page_count,
    )
    extraction = extractor.extract(source, BytesIO(content))
    page_count = len(extraction.document.pages)
    text_block_count = sum(
        block.kind == "text" and block.text is not None
        for page in extraction.document.pages
        for block in page.blocks
    )
    if (
        page_count > maximum_page_count
        or text_block_count > maximum_block_count
    ):
        raise ValueError(
            "extracted evidence exceeds requested narrowing bounds"
        )
    reading_projection = derive_native_pdf_reading_projection(
        extraction=extraction,
        source_artifact=source_artifact,
        pipeline_configuration_id=pipeline_configuration_id,
    )
    source_result = derive_native_pdf_source_result(
        projection=reading_projection,
        source_artifact=source_artifact,
        artifact_verification=artifact_verification,
        configuration=configuration,
    )
    page_projection = PageProjectionActionizer().action(
        request=PageProjectionRequest(
            source_result=source_result,
            artifact_verification_result=artifact_verification,
            include_figure_captions=False,
        )
    )
    enrichment = PageProjectionEvidenceEnrichmentActionizer().action(
        request=PageProjectionEvidenceEnrichmentRequest(
            projection=page_projection
        )
    )
    return PageProjectionPublicationEvidence(
        extraction_manifest_id=extraction.manifest.manifest_id,
        extracted_document_id=extraction.document.document_id,
        extraction_warning_count=len(extraction.warnings),
        extraction_warning_codes=PageProjectionPublicationCodeInventory(
            *sorted({warning.code for warning in extraction.warnings})
        ),
        enrichment=enrichment,
    )


def derive_native_pdf_reading_projection(
    *,
    extraction: ExtractionResult,
    source_artifact: ManagedArtifactReference,
    pipeline_configuration_id: str,
) -> ReadingEvidenceProjectionResult:
    """Project exact native text blocks into current reading evidence."""
    source_id = ReadingEvidenceIdentity(
        kind=ReadingEvidenceIdentityKind.SOURCE,
        value=extraction.document.source.source_id,
    )
    extraction_id = ReadingEvidenceIdentity(
        kind=ReadingEvidenceIdentityKind.EXTRACTION_RESULT,
        value=extraction.manifest.manifest_id,
    )
    producer_ids = {
        role: ReadingEvidenceIdentityDerivation.derive(
            kind=ReadingEvidenceIdentityKind.PRODUCER,
            prefix=f"native-pdf-{role}-producer",
            material={
                "pipeline_configuration_id": pipeline_configuration_id,
                "role": role,
            },
        )
        for role in ("document", "page-text", "structure", "clean-text")
    }
    document = ReadingDocumentProducerEvidence(
        document_id=ReadingEvidenceIdentity(
            kind=ReadingEvidenceIdentityKind.DOCUMENT,
            value=extraction.document.document_id,
        ),
        source_id=source_id,
        source_artifact=source_artifact,
        title=f"PDF source {source_artifact.sha256[:16]}",
        expected_page_count=len(extraction.document.pages),
        extraction_result_id=extraction_id,
        producer_id=producer_ids["document"],
        producer_version="1.0",
    )
    page_records: list[ReadingPageTextProducerEvidence] = []
    structured_records: list[ReadingStructuredItemProducerEvidence] = []
    clean_records: list[ReadingCleanTextProducerEvidence] = []
    geometry_warning_ids: list[ReadingEvidenceIdentity] = []
    for page in extraction.document.pages:
        location = ReadingPageLocation(
            physical_page_index=page.page_index,
            printed_page_label=page.printed_page_label,
        )
        text_blocks = tuple(
            block
            for block in page.blocks
            if block.kind == "text" and block.text is not None
        )
        stream = ReadingTextStreamEvidence(
            kind=ReadingTextStreamKind.NATIVE,
            page_location=location,
            text="\n".join(
                block.text for block in text_blocks if block.text is not None
            ),
            upstream_id=extraction_id,
            producer_id=producer_ids["page-text"],
            composition_id=None,
            automated=True,
            accepted=False,
            review_status=ReadingReviewStatus.UNREVIEWED,
        )
        streams = ReadingTextStreamEvidenceInventory(stream)
        page_record = ReadingPageTextProducerEvidence(
            streams=streams,
            selection=ReadingTextSelection(
                streams=streams,
                selected_stream_id=stream.stream_id,
                basis=ReadingTextSelectionBasis.NATIVE_EXACT,
            ),
            producer_id=producer_ids["page-text"],
            producer_version="1.0",
            review_status=ReadingReviewStatus.UNREVIEWED,
        )
        page_records.append(page_record)
        for order_index, block in enumerate(text_blocks):
            assert block.text is not None
            block_id = ReadingEvidenceIdentity(
                kind=ReadingEvidenceIdentityKind.SOURCE_BLOCK,
                value=block.block_id,
            )
            structured_records.append(
                ReadingStructuredItemProducerEvidence(
                    page_location=location,
                    order_index=order_index,
                    kind=ReadingStructuredItemKind.PARAGRAPH,
                    source_block_ids=ReadingSourceBlockIdentityInventory(
                        block_id
                    ),
                    source_object_id=None,
                    producer_id=producer_ids["structure"],
                    producer_version="1.0",
                )
            )
            spans: list[ReadingSourceSpanEvidence] = []
            block_warnings: list[ReadingEvidenceIdentity] = []
            for span_index, span in enumerate(block.source_spans):
                evidence_span = derive_native_pdf_source_span(
                    span=span,
                    source_id=source_id,
                    page_location=location,
                    page_width=page.width,
                    page_height=page.height,
                    source_block_id=block.block_id,
                    span_index=span_index,
                )
                spans.append(evidence_span)
                if evidence_span.geometry_warning_id is not None:
                    block_warnings.append(evidence_span.geometry_warning_id)
                    geometry_warning_ids.append(
                        evidence_span.geometry_warning_id
                    )
            warning_ids = tuple(
                sorted(block_warnings, key=lambda value: value.value)
            )
            clean_records.append(
                ReadingCleanTextProducerEvidence(
                    selected_stream_id=stream.stream_id,
                    source_block_id=block_id,
                    page_location=location,
                    order_index=order_index,
                    raw_text=block.text,
                    clean_text=block.text,
                    transformations=ReadingTextTransformationInventory(),
                    source_spans=ReadingSourceSpanEvidenceInventory(*spans),
                    warning_ids=ReadingEvidenceIdentityInventory(
                        ReadingEvidenceIdentityKind.WARNING,
                        *warning_ids,
                    ),
                    producer_id=producer_ids["clean-text"],
                    producer_version="1.0",
                )
            )
    page_text = ReadingPageTextProducerEvidenceInventory(*page_records)
    structured = ReadingStructuredItemProducerEvidenceInventory(
        *structured_records
    )
    clean_text = ReadingCleanTextProducerEvidenceInventory(*clean_records)
    figures = ReadingFigureProducerEvidenceInventory()
    tables = ReadingTableProducerEvidenceInventory()
    equations = ReadingEquationProducerEvidenceInventory()
    managed = ManagedArtifactReferenceInventory(source_artifact)
    projection_configuration = ReadingEvidenceProjectionConfiguration()
    inventory_inputs: tuple[tuple[str, list[str]], ...] = (
        ("page_text", [value.record_id.value for value in page_records]),
        (
            "structured_items",
            [value.record_id.value for value in structured_records],
        ),
        ("clean_text", [value.record_id.value for value in clean_records]),
        ("figures", []),
        ("tables", []),
        ("equations", []),
    )
    inventory_ids = tuple(
        ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
            role=role,
            identities=identities,
        )
        for role, identities in inventory_inputs
    )
    lineage = ReadingEvidenceLineage(
        source_artifact=source_artifact,
        extraction_result_id=document.extraction_result_id,
        document_producer_id=document.record_id,
        page_text_inventory_id=inventory_ids[0],
        structured_item_inventory_id=inventory_ids[1],
        clean_text_inventory_id=inventory_ids[2],
        figure_inventory_id=inventory_ids[3],
        table_inventory_id=inventory_ids[4],
        equation_inventory_id=inventory_ids[5],
        projection_configuration_id=projection_configuration.configuration_id,
        managed_artifacts=managed,
    )
    pages: list[ReadingEvidencePage] = []
    clean_by_block = {value.source_block_id: value for value in clean_records}
    structured_by_page: dict[
        int, list[ReadingStructuredItemProducerEvidence]
    ] = {}
    for value in structured_records:
        structured_by_page.setdefault(
            value.page_location.physical_page_index, []
        ).append(value)
    for page_record in page_records:
        page_index = page_record.streams.page_location.physical_page_index
        blocks = [
            ReadingTextEvidenceBlock(
                structured_item=item,
                sources=ReadingTextBlockSourceInventory(
                    clean_by_block[next(iter(item.source_block_ids))]
                ),
                basis=projection_configuration.text_basis,
            )
            for item in structured_by_page.get(page_index, [])
        ]
        pages.append(
            ReadingEvidencePage(
                page_text=page_record,
                blocks=ReadingEvidenceBlockInventory(*blocks),
            )
        )
    page_inventory = ReadingEvidencePageInventory(*pages)
    limitations = derive_native_pdf_reading_limitations(
        warning_ids=geometry_warning_ids
    )
    canonical_blocks = tuple(
        block
        for canonical_page in pages
        for block in canonical_page.blocks
        if type(block) is ReadingTextEvidenceBlock
    )
    canonical_streams = tuple(
        stream
        for canonical_page in pages
        for stream in canonical_page.page_text.streams
    )
    text_values = (
        *(stream.text for stream in canonical_streams),
        *(block.text for block in canonical_blocks),
    )
    expected = ExpectedReadingEvidenceInventory(
        measures=ReadingEvidenceInventoryMeasures(
            page_count=len(pages),
            stream_count=len(canonical_streams),
            selection_count=len(pages),
            block_count=len(canonical_blocks),
            paragraph_count=len(canonical_blocks),
            heading_count=0,
            figure_count=0,
            table_count=0,
            equation_count=0,
            caption_count=0,
            gate_count=0,
            association_count=0,
            artifact_count=1,
            character_count=sum(len(value) for value in text_values),
            utf8_byte_count=sum(len(value.encode()) for value in text_values),
            limitation_count=len(limitations),
            pages_sha256=ReadingEvidenceInventory.digest_identity_material(
                page_inventory.identity_material()
            ),
            blocks_sha256=ReadingEvidenceInventory.digest_identity_material(
                [block.block_id.value for block in canonical_blocks]
            ),
            producers_sha256=ReadingEvidenceInventory.digest_identity_material(
                [
                    document.record_id.value,
                    *(value.value for value in inventory_ids),
                ]
            ),
            artifacts_sha256=ReadingEvidenceInventory.digest_identity_material(
                [source_artifact.artifact_id]
            ),
            limitations_sha256=ReadingEvidenceInventory.digest_identity_material(
                limitations.identity_material()
            ),
            lineage_id=lineage.lineage_id,
        )
    )
    return ReadingEvidenceProjectionActionizer().action(
        request=ReadingEvidenceProjectionRequest(
            document=document,
            page_text=page_text,
            structured_items=structured,
            clean_text=clean_text,
            figures=figures,
            tables=tables,
            equations=equations,
            managed_artifacts=managed,
            expected_inventory=expected,
            configuration=projection_configuration,
            limits=READING_EVIDENCE_LIMITS,
        )
    )


def derive_native_pdf_source_span(
    *,
    span: SourceSpan,
    source_id: ReadingEvidenceIdentity,
    page_location: ReadingPageLocation,
    page_width: float,
    page_height: float,
    source_block_id: str,
    span_index: int,
) -> ReadingSourceSpanEvidence:
    """Normalize one exact extraction span without synthesizing geometry."""
    bounding_box = None
    geometry_warning_id = None
    if span.bounding_box is not None:
        x0, y0, x1, y1 = (float(value) for value in span.bounding_box)
        normalized = (
            x0 / page_width,
            y0 / page_height,
            x1 / page_width,
            y1 / page_height,
        )
        if (
            0.0 <= normalized[0] < normalized[2] <= 1.0
            and 0.0 <= normalized[1] < normalized[3] <= 1.0
        ):
            bounding_box = ReadingBoundingBox(*normalized)
        else:
            geometry_warning_id = ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.WARNING,
                prefix="reading-native-pdf-geometry-warning",
                material={
                    "bounding_box": list(span.bounding_box),
                    "page_height": page_height,
                    "page_width": page_width,
                    "source_block_id": source_block_id,
                    "span_index": span_index,
                },
            )
    return ReadingSourceSpanEvidence(
        source_id=source_id,
        page_location=page_location,
        bounding_box=bounding_box,
        geometry_warning_id=geometry_warning_id,
        start_offset=span.start_offset,
        end_offset=span.end_offset,
    )


def derive_native_pdf_reading_limitations(
    *, warning_ids: list[ReadingEvidenceIdentity]
) -> ReadingEvidenceLimitationInventory:
    """Derive the exact geometry limitation emitted by the current projector."""
    unique = tuple(
        sorted(
            set(warning_ids), key=lambda value: (value.kind.value, value.value)
        )
    )
    if not unique:
        return ReadingEvidenceLimitationInventory()
    limitation = ReadingEvidenceLimitation(
        code=ReadingEvidenceLimitationCode.INVALID_GEOMETRY_OMITTED,
        affected_ids=ReadingAffectedEvidenceIdentityInventory(*unique),
    )
    return ReadingEvidenceLimitationInventory(limitation)


def derive_native_pdf_source_result(
    *,
    projection: ReadingEvidenceProjectionResult,
    source_artifact: ManagedArtifactReference,
    artifact_verification: ManagedArtifactVerificationResult,
    configuration: PageProjectionPublicationConfiguration,
) -> ReadingEvidenceSourceResult:
    """Bind one in-process current projection to exact verification evidence."""
    request = ReadingEvidenceSourceRequest(
        provider_source_id=source_artifact.artifact_id,
        document_id=projection.document.document_id,
        projection_result_id=projection.result_id,
        inventory_id=projection.inventory.inventory_id,
        maximum_page_count=configuration.maximum_page_count,
        maximum_block_count=configuration.maximum_block_count,
        maximum_artifact_count=1,
        maximum_provider_record_count=READING_EVIDENCE_LIMITS.maximum_records,
        authority_id=configuration.authority_id,
    )
    return ReadingEvidenceSourceResult(
        request=request,
        document=projection.document,
        inventory=projection.inventory,
        projection_result_id=projection.result_id,
        provider_implementation_id=(
            "page-projection-publication-current-source-provider:1.0"
        ),
        provider_verification_id=artifact_verification.result_id,
    )
