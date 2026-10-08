"""Semantic fixture owner for canonical reading evidence projection."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.source import (  # noqa: E501
    ReadingTextBlockSourceInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.inventory.expected import (  # noqa: E501
    ExpectedReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.measures import (  # noqa: E501
    ReadingEvidenceInventoryMeasures,
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
from projectkoios.ingestion.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceProjectionConfiguration,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.request import (  # noqa: E501
    ReadingEvidenceProjectionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)

from tests.projectkoios.ingestion.transcript.reading.evidence.fixture import (
    ReadingEvidenceFoundationFixture,
)


def digest_expected_identity_material(identities: object) -> SHA256Hash:
    return SHA256Fingerprinter.fingerprint(
        content=CanonicalJsonSerializer.serialize_bytes(identities)
    )


@dataclass(frozen=True, slots=True)
class ReadingEvidenceProjectionFixture:
    """Own one complete exact paragraph-only projection request."""

    foundation: ReadingEvidenceFoundationFixture
    request: ReadingEvidenceProjectionRequest

    @classmethod
    def build(cls) -> ReadingEvidenceProjectionFixture:
        """Build independent expected evidence and its producer request."""
        foundation = ReadingEvidenceFoundationFixture()
        source_artifact = ManagedArtifactReference(
            sha256=foundation.digest,
            byte_length=256,
            media_type=ManagedArtifactMediaType.APPLICATION_PDF,
        )
        managed = ManagedArtifactReferenceInventory(source_artifact)
        document = ReadingDocumentProducerEvidence(
            document_id=foundation.identity(
                ReadingEvidenceIdentityKind.DOCUMENT, "book"
            ),
            source_id=foundation.identity(
                ReadingEvidenceIdentityKind.SOURCE, "book"
            ),
            source_artifact=source_artifact,
            title="Evidence book",
            expected_page_count=1,
            extraction_result_id=foundation.identity(
                ReadingEvidenceIdentityKind.EXTRACTION_RESULT, "native"
            ),
            producer_id=foundation.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "document"
            ),
            producer_version="1",
        )
        streams = foundation.native_streams()
        page_text_record = ReadingPageTextProducerEvidence(
            streams=streams,
            selection=foundation.native_selection(streams),
            producer_id=foundation.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "page-text"
            ),
            producer_version="1",
            review_status=ReadingReviewStatus.UNREVIEWED,
        )
        page_text = ReadingPageTextProducerEvidenceInventory(page_text_record)
        source_block_id = foundation.identity(
            ReadingEvidenceIdentityKind.SOURCE_BLOCK, "paragraph"
        )
        structured_record = ReadingStructuredItemProducerEvidence(
            page_location=foundation.page(),
            order_index=0,
            kind=ReadingStructuredItemKind.PARAGRAPH,
            source_block_ids=ReadingSourceBlockIdentityInventory(
                source_block_id
            ),
            source_object_id=None,
            producer_id=foundation.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "structure"
            ),
            producer_version="1",
        )
        structured = ReadingStructuredItemProducerEvidenceInventory(
            structured_record
        )
        clean_record = ReadingCleanTextProducerEvidence(
            selected_stream_id=page_text_record.selection.selected_stream_id,
            source_block_id=source_block_id,
            page_location=foundation.page(),
            order_index=0,
            raw_text="Canonical paragraph.",
            clean_text="Canonical paragraph.",
            transformations=ReadingTextTransformationInventory(),
            source_spans=foundation.text_source_spans(),
            warning_ids=foundation.warning_ids(),
            producer_id=foundation.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "clean"
            ),
            producer_version="1",
        )
        clean = ReadingCleanTextProducerEvidenceInventory(clean_record)
        figures = ReadingFigureProducerEvidenceInventory()
        tables = ReadingTableProducerEvidenceInventory()
        equations = ReadingEquationProducerEvidenceInventory()
        configuration = ReadingEvidenceProjectionConfiguration()
        inventory_inputs = (
            ("page_text", [page_text_record.record_id.value]),
            ("structured_items", [structured_record.record_id.value]),
            ("clean_text", [clean_record.record_id.value]),
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
            projection_configuration_id=configuration.configuration_id,
            managed_artifacts=managed,
        )
        text_block = ReadingTextEvidenceBlock(
            structured_item=structured_record,
            sources=ReadingTextBlockSourceInventory(clean_record),
            basis=configuration.text_basis,
        )
        pages = ReadingEvidencePageInventory(
            ReadingEvidencePage(
                page_text=page_text_record,
                blocks=ReadingEvidenceBlockInventory(text_block),
            )
        )
        limitations = ReadingEvidenceLimitationInventory()
        text_values = (next(iter(streams)).text, text_block.text)
        expected = ExpectedReadingEvidenceInventory(
            measures=ReadingEvidenceInventoryMeasures(
                page_count=1,
                stream_count=1,
                selection_count=1,
                block_count=1,
                paragraph_count=1,
                heading_count=0,
                figure_count=0,
                table_count=0,
                equation_count=0,
                caption_count=0,
                gate_count=0,
                association_count=0,
                artifact_count=1,
                character_count=sum(len(value) for value in text_values),
                utf8_byte_count=sum(
                    len(value.encode()) for value in text_values
                ),
                limitation_count=0,
                pages_sha256=digest_expected_identity_material(
                    pages.identity_material()
                ),
                blocks_sha256=digest_expected_identity_material(
                    [text_block.block_id.value]
                ),
                producers_sha256=digest_expected_identity_material(
                    [
                        document.record_id.value,
                        *(value.value for value in inventory_ids),
                    ]
                ),
                artifacts_sha256=digest_expected_identity_material(
                    [value.artifact_id for value in managed]
                ),
                limitations_sha256=digest_expected_identity_material(
                    limitations.identity_material()
                ),
                lineage_id=lineage.lineage_id,
            )
        )
        return cls(
            foundation=foundation,
            request=ReadingEvidenceProjectionRequest(
                document=document,
                page_text=page_text,
                structured_items=structured,
                clean_text=clean,
                figures=figures,
                tables=tables,
                equations=equations,
                managed_artifacts=managed,
                expected_inventory=expected,
                configuration=configuration,
                limits=READING_EVIDENCE_LIMITS,
            ),
        )
