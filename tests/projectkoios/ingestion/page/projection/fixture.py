"""Semantic fixtures for current-schema page projection tests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.disposition import (  # noqa: E501
    ReadingEquationSelectionDisposition,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.gate import (
    ReadingEquationGate,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.status import (
    ReadingEquationRecognitionStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.evidence import (  # noqa: E501
    ReadingEquationProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.inventory import (  # noqa: E501
    ReadingEquationProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.source import (  # noqa: E501
    ReadingSourceBlockIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.evidence import (  # noqa: E501
    ReadingTableProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.actionizer import (  # noqa: E501
    ReadingEvidenceProjectionActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.result import (  # noqa: E501
    ReadingEvidenceProjectionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.table.boundary import (
    ReadingTableBoundaryKind,
)

from tests.projectkoios.ingestion.transcript.reading.evidence.fixture import (
    ReadingEvidenceFoundationFixture,
)
from tests.projectkoios.ingestion.transcript.reading.evidence.projection.visual_fixture import (  # noqa: E501
    ReadingVisualProjectionFixture,
)


@dataclass(frozen=True, slots=True)
class PageProjectionMixedVisualFixture:
    """Own one valid text, figure, table, and equation canonical document."""

    canonical: ReadingEvidenceProjectionResult
    foundation: ReadingEvidenceFoundationFixture
    document: ReadingEvidenceDocument = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "document", self.derive_document())

    @classmethod
    def build(cls) -> PageProjectionMixedVisualFixture:
        """Build one complete mixed canonical fixture."""
        projection = ReadingVisualProjectionFixture.build()
        canonical = ReadingEvidenceProjectionActionizer().action(
            request=projection.request
        )
        return cls(
            canonical=canonical,
            foundation=ReadingEvidenceFoundationFixture(),
        )

    def derive_table_block(self) -> ReadingTableEvidenceBlock:
        """Return one valid non-emittable canonical table block."""
        page = next(iter(self.canonical.document.pages))
        source_object_id = self.foundation.identity(
            ReadingEvidenceIdentityKind.SOURCE_OBJECT,
            "table",
        )
        item = ReadingStructuredItemProducerEvidence(
            page_location=page.page_location,
            order_index=2,
            kind=ReadingStructuredItemKind.TABLE,
            source_block_ids=ReadingSourceBlockIdentityInventory(),
            source_object_id=source_object_id,
            producer_id=self.foundation.identity(
                ReadingEvidenceIdentityKind.PRODUCER,
                "structure",
            ),
            producer_version="1",
        )
        producer = ReadingTableProducerEvidence(
            candidate_id=self.foundation.identity(
                ReadingEvidenceIdentityKind.CANDIDATE,
                "table",
            ),
            region_id=self.foundation.identity(
                ReadingEvidenceIdentityKind.REGION,
                "table",
            ),
            boundary_kind=ReadingTableBoundaryKind.RULED,
            lineage=self.foundation.producer_lineage(
                source_object_id=source_object_id,
                page=page.page_location,
                producer_token="table",
            ),
            assessment=self.foundation.visual_assessment(
                page=page.page_location
            ),
        )
        return ReadingTableEvidenceBlock(
            structured_item=item,
            producer_evidence=producer,
        )

    def derive_equation_block(self) -> ReadingEquationEvidenceBlock:
        """Return one valid non-emittable canonical equation block."""
        page = next(iter(self.canonical.document.pages))
        source_object_id = self.foundation.identity(
            ReadingEvidenceIdentityKind.SOURCE_OBJECT,
            "equation",
        )
        item = ReadingStructuredItemProducerEvidence(
            page_location=page.page_location,
            order_index=3,
            kind=ReadingStructuredItemKind.EQUATION,
            source_block_ids=ReadingSourceBlockIdentityInventory(),
            source_object_id=source_object_id,
            producer_id=self.foundation.identity(
                ReadingEvidenceIdentityKind.PRODUCER,
                "structure",
            ),
            producer_version="1",
        )
        producer = ReadingEquationProducerEvidence(
            assembly_id=self.foundation.identity(
                ReadingEvidenceIdentityKind.ASSEMBLY,
                "equation",
            ),
            candidate_id=self.foundation.identity(
                ReadingEvidenceIdentityKind.CANDIDATE,
                "equation",
            ),
            lineage=self.foundation.producer_lineage(
                source_object_id=source_object_id,
                page=page.page_location,
                producer_token="equation",
            ),
            native_representation="E = mc^2",
            recognized_representation=None,
            selection_disposition=(ReadingEquationSelectionDisposition.PRIMARY),
            recognition_status=ReadingEquationRecognitionStatus.NOT_REQUESTED,
            gate=ReadingEquationGate(
                review_status=ReadingReviewStatus.UNREVIEWED,
                accepted=False,
                review_required=True,
                chunk_text_eligible=False,
            ),
        )
        return ReadingEquationEvidenceBlock(
            structured_item=item,
            producer_evidence=producer,
        )

    def derive_document(self) -> ReadingEvidenceDocument:
        """Return the exact mixed document with synchronized lineage."""
        document = self.canonical.document
        page = next(iter(document.pages))
        table_block = self.derive_table_block()
        equation_block = self.derive_equation_block()
        mixed_blocks = (*page.blocks, table_block, equation_block)
        pages = ReadingEvidencePageInventory(
            ReadingEvidencePage(
                page_text=page.page_text,
                blocks=ReadingEvidenceBlockInventory(*mixed_blocks),
            )
        )
        tables = ReadingTableProducerEvidenceInventory(
            table_block.producer_evidence
        )
        equations = ReadingEquationProducerEvidenceInventory(
            equation_block.producer_evidence
        )
        references = {
            value.artifact_id: value for value in document.managed_artifacts
        }
        for producer in (
            table_block.producer_evidence,
            equation_block.producer_evidence,
        ):
            for reference in producer.lineage.artifacts:
                references[reference.artifact_id] = reference
        managed_artifacts = ManagedArtifactReferenceInventory(
            *sorted(references.values(), key=lambda value: value.artifact_id)
        )
        lineage = replace(
            document.lineage,
            structured_item_inventory_id=(
                ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                    role="structured_items",
                    identities=[
                        block.structured_item.record_id.value
                        for block in mixed_blocks
                    ],
                )
            ),
            table_inventory_id=(
                ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                    role="tables",
                    identities=tables.identity_material(),
                )
            ),
            equation_inventory_id=(
                ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                    role="equations",
                    identities=equations.identity_material(),
                )
            ),
            managed_artifacts=managed_artifacts,
        )
        return replace(
            document,
            pages=pages,
            retained_tables=tables,
            retained_equations=equations,
            managed_artifacts=managed_artifacts,
            lineage=lineage,
        )
