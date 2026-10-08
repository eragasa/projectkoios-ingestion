"""Semantic fixture owner for canonical visual projection evidence."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.association.evidence import (  # noqa: E501
    ReadingAssociationEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.association.inventory import (  # noqa: E501
    ReadingAssociationEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.association.role import (  # noqa: E501
    ReadingAssociationRole,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
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
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.input.visual.assessment import (  # noqa: E501
    ReadingVisualAssessment,
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
from projectkoios.ingestion.transcript.reading.evidence.lineage.definition import (  # noqa: E501
    ReadingEvidenceLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.request import (  # noqa: E501
    ReadingEvidenceProjectionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.span.evidence import (
    ReadingSourceSpanEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.status.visual import (
    ReadingVisualEvidenceStatus,
)

from .fixture import (
    ReadingEvidenceProjectionFixture,
    digest_expected_identity_material,
)


@dataclass(frozen=True, slots=True)
class ReadingVisualProjectionFixture:
    """Own one complete paragraph-and-figure projection request."""

    request: ReadingEvidenceProjectionRequest

    @classmethod
    def build(cls) -> ReadingVisualProjectionFixture:
        """Build expected text, caption, and limitation evidence."""
        base = ReadingEvidenceProjectionFixture.build()
        request = base.request
        foundation = base.foundation
        clean_record = next(iter(request.clean_text))
        paragraph_item = next(iter(request.structured_items))
        figure_object_id = foundation.identity(
            ReadingEvidenceIdentityKind.SOURCE_OBJECT, "figure"
        )
        association_span = ReadingSourceSpanEvidence(
            source_id=request.document.source_id,
            page_location=foundation.page(),
            start_offset=0,
            end_offset=len(clean_record.clean_text),
        )
        association = ReadingAssociationEvidence(
            role=ReadingAssociationRole.CAPTION,
            text="Figure title",
            source_block_ids=ReadingEvidenceIdentityInventory(
                ReadingEvidenceIdentityKind.SOURCE_BLOCK,
                clean_record.source_block_id,
            ),
            source_spans=ReadingSourceSpanEvidenceInventory(association_span),
            producer_association_id=foundation.identity(
                ReadingEvidenceIdentityKind.ASSOCIATION, "figure-caption"
            ),
        )
        visual_artifact = foundation.artifact()
        figure = ReadingFigureProducerEvidence(
            candidate_id=foundation.identity(
                ReadingEvidenceIdentityKind.CANDIDATE, "figure"
            ),
            lineage=foundation.producer_lineage(
                source_object_id=figure_object_id,
            ),
            assessment=ReadingVisualAssessment(
                associations=ReadingAssociationEvidenceInventory(association),
                confidence=0.9,
                visual_status=ReadingVisualEvidenceStatus.PROPOSED,
                review_status=ReadingReviewStatus.UNREVIEWED,
            ),
        )
        figure_item = ReadingStructuredItemProducerEvidence(
            page_location=foundation.page(),
            order_index=1,
            kind=ReadingStructuredItemKind.FIGURE,
            source_block_ids=ReadingSourceBlockIdentityInventory(),
            source_object_id=figure_object_id,
            producer_id=foundation.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "structure"
            ),
            producer_version="1",
        )
        structured = ReadingStructuredItemProducerEvidenceInventory(
            paragraph_item,
            figure_item,
        )
        figures = ReadingFigureProducerEvidenceInventory(figure)
        managed = ManagedArtifactReferenceInventory(
            *sorted(
                (request.document.source_artifact, visual_artifact),
                key=lambda value: value.artifact_id,
            )
        )
        inventory_inputs = (
            (
                "page_text",
                [value.record_id.value for value in request.page_text],
            ),
            (
                "structured_items",
                [value.record_id.value for value in structured],
            ),
            (
                "clean_text",
                [value.record_id.value for value in request.clean_text],
            ),
            ("figures", [figure.record_id.value]),
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
            source_artifact=request.document.source_artifact,
            extraction_result_id=request.document.extraction_result_id,
            document_producer_id=request.document.record_id,
            page_text_inventory_id=inventory_ids[0],
            structured_item_inventory_id=inventory_ids[1],
            clean_text_inventory_id=inventory_ids[2],
            figure_inventory_id=inventory_ids[3],
            table_inventory_id=inventory_ids[4],
            equation_inventory_id=inventory_ids[5],
            projection_configuration_id=request.configuration.configuration_id,
            managed_artifacts=managed,
        )
        caption = ReadingCaptionEvidence(
            text=association.text,
            association_ids=ReadingEvidenceIdentityInventory(
                ReadingEvidenceIdentityKind.ASSOCIATION,
                association.association_id,
            ),
            basis=request.configuration.caption_basis,
        )
        text_block = ReadingTextEvidenceBlock(
            structured_item=paragraph_item,
            sources=ReadingTextBlockSourceInventory(clean_record),
            basis=request.configuration.text_basis,
        )
        figure_block = ReadingFigureEvidenceBlock(
            structured_item=figure_item,
            producer_evidence=figure,
            caption=caption,
        )
        page_text = next(iter(request.page_text))
        pages = ReadingEvidencePageInventory(
            ReadingEvidencePage(
                page_text=page_text,
                blocks=ReadingEvidenceBlockInventory(text_block, figure_block),
            )
        )
        limitation = ReadingEvidenceLimitation(
            code=ReadingEvidenceLimitationCode.UNREVIEWED_VISUAL_EVIDENCE,
            affected_ids=ReadingAffectedEvidenceIdentityInventory(
                figure.record_id
            ),
        )
        limitations = ReadingEvidenceLimitationInventory(limitation)
        streams = tuple(page_text.streams)
        text_values = (
            *(stream.text for stream in streams),
            text_block.text,
            association.text,
        )
        expected = ExpectedReadingEvidenceInventory(
            measures=ReadingEvidenceInventoryMeasures(
                page_count=1,
                stream_count=len(streams),
                selection_count=1,
                block_count=2,
                paragraph_count=1,
                heading_count=0,
                figure_count=1,
                table_count=0,
                equation_count=0,
                caption_count=1,
                gate_count=0,
                association_count=1,
                artifact_count=len(managed),
                character_count=sum(len(value) for value in text_values),
                utf8_byte_count=sum(
                    len(value.encode()) for value in text_values
                ),
                limitation_count=1,
                pages_sha256=digest_expected_identity_material(
                    pages.identity_material()
                ),
                blocks_sha256=digest_expected_identity_material(
                    [text_block.block_id.value, figure_block.block_id.value]
                ),
                producers_sha256=digest_expected_identity_material(
                    [
                        request.document.record_id.value,
                        lineage.page_text_inventory_id.value,
                        lineage.structured_item_inventory_id.value,
                        lineage.clean_text_inventory_id.value,
                        lineage.figure_inventory_id.value,
                        lineage.table_inventory_id.value,
                        lineage.equation_inventory_id.value,
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
            request=ReadingEvidenceProjectionRequest(
                document=request.document,
                page_text=request.page_text,
                structured_items=structured,
                clean_text=request.clean_text,
                figures=figures,
                tables=request.tables,
                equations=request.equations,
                managed_artifacts=managed,
                expected_inventory=expected,
                configuration=request.configuration,
                limits=request.limits,
            )
        )
