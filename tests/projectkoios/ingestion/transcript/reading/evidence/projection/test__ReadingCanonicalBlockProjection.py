import pytest
from projectkoios.ingestion.transcript.reading.evidence.block.equation.projection import (  # noqa: E501
    project_reading_equation_evidence_block,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.projection import (  # noqa: E501
    project_reading_table_evidence_block,
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
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
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
from projectkoios.ingestion.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceProjectionConfiguration,
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


def test__table_block_projection__enforces_visual_admission() -> None:
    fixture = ReadingEvidenceFoundationFixture()
    source_object_id = fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "table"
    )
    item = ReadingStructuredItemProducerEvidence(
        page_location=fixture.page(),
        order_index=0,
        kind=ReadingStructuredItemKind.TABLE,
        source_block_ids=ReadingSourceBlockIdentityInventory(),
        source_object_id=source_object_id,
        producer_id=fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "structure"
        ),
        producer_version="1",
    )
    producer = ReadingTableProducerEvidence(
        candidate_id=fixture.identity(
            ReadingEvidenceIdentityKind.CANDIDATE, "table"
        ),
        region_id=fixture.identity(ReadingEvidenceIdentityKind.REGION, "table"),
        boundary_kind=ReadingTableBoundaryKind.RULED,
        lineage=fixture.producer_lineage(
            source_object_id=source_object_id,
            producer_token="table",
        ),
        assessment=fixture.visual_assessment(),
    )
    tables = ReadingTableProducerEvidenceInventory(producer)

    block = project_reading_table_evidence_block(
        item=item,
        tables=tables,
        configuration=ReadingEvidenceProjectionConfiguration(),
    )

    assert block.producer_evidence == producer
    with pytest.raises(ReadingEvidenceError, match="inadmissible"):
        project_reading_table_evidence_block(
            item=item,
            tables=tables,
            configuration=ReadingEvidenceProjectionConfiguration(
                retain_proposed_visual_evidence=False,
            ),
        )


def test__equation_block_projection__requires_configured_disposition() -> None:
    fixture = ReadingEvidenceFoundationFixture()
    source_object_id = fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "equation"
    )
    item = ReadingStructuredItemProducerEvidence(
        page_location=fixture.page(),
        order_index=0,
        kind=ReadingStructuredItemKind.EQUATION,
        source_block_ids=ReadingSourceBlockIdentityInventory(),
        source_object_id=source_object_id,
        producer_id=fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "structure"
        ),
        producer_version="1",
    )
    producer = ReadingEquationProducerEvidence(
        assembly_id=fixture.identity(
            ReadingEvidenceIdentityKind.ASSEMBLY, "equation"
        ),
        candidate_id=fixture.identity(
            ReadingEvidenceIdentityKind.CANDIDATE, "equation"
        ),
        lineage=fixture.producer_lineage(
            source_object_id=source_object_id,
            producer_token="equation",
        ),
        native_representation="E = mc^2",
        recognized_representation=None,
        selection_disposition=ReadingEquationSelectionDisposition.PRIMARY,
        recognition_status=ReadingEquationRecognitionStatus.NOT_REQUESTED,
        gate=ReadingEquationGate(
            review_status=ReadingReviewStatus.UNREVIEWED,
            accepted=False,
            review_required=True,
            chunk_text_eligible=False,
        ),
    )
    equations = ReadingEquationProducerEvidenceInventory(producer)

    block = project_reading_equation_evidence_block(
        item=item,
        equations=equations,
        disposition=ReadingEquationSelectionDisposition.PRIMARY,
    )

    assert block.producer_evidence.gate.review_required
    with pytest.raises(ReadingEvidenceError, match="configured disposition"):
        project_reading_equation_evidence_block(
            item=item,
            equations=equations,
            disposition=ReadingEquationSelectionDisposition.AUXILIARY,
        )
