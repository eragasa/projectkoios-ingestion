import pytest
from projectkoios.ingestion.transcript.reading.evidence.equation.disposition import (  # noqa: E501
    ReadingEquationSelectionDisposition,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.gate import (
    ReadingEquationGate,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.status import (
    ReadingEquationRecognitionStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.evidence import (  # noqa: E501
    ReadingTableProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.table.boundary import (
    ReadingTableBoundaryKind,
)

from .fixture import ReadingEvidenceFoundationFixture


def test__figure_and_table_producers__retain_unordered_exact_evidence(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    page = reading_evidence_fixture.page()
    figure_object = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "figure"
    )
    table_object = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "table"
    )
    figure = ReadingFigureProducerEvidence(
        candidate_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.CANDIDATE, "figure"
        ),
        lineage=reading_evidence_fixture.producer_lineage(
            source_object_id=figure_object,
            page=page,
        ),
        assessment=reading_evidence_fixture.visual_assessment(page=page),
    )
    table = ReadingTableProducerEvidence(
        candidate_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.CANDIDATE, "table"
        ),
        region_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.REGION, "table"
        ),
        boundary_kind=ReadingTableBoundaryKind.RULED,
        lineage=reading_evidence_fixture.producer_lineage(
            source_object_id=table_object,
            page=page,
        ),
        assessment=reading_evidence_fixture.visual_assessment(
            page=page,
            confidence=0.8,
            visual_status=ReadingVisualEvidenceStatus.OBSERVED,
            review_status=ReadingReviewStatus.ACCEPTED,
        ),
    )

    assert len(ReadingFigureProducerEvidenceInventory(figure)) == 1
    assert len(ReadingTableProducerEvidenceInventory(table)) == 1
    assert table.boundary_kind is ReadingTableBoundaryKind.RULED


def test__figure_producer__rejects_mismatched_source_object(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    page = reading_evidence_fixture.page()
    expected = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "expected"
    )
    another = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "another"
    )

    with pytest.raises(ValueError, match="lineage"):
        reading_evidence_fixture.producer_lineage(
            source_object_id=expected,
            page=page,
            source_spans=reading_evidence_fixture.source_spans(
                source_object_id=another,
                page=page,
            ),
        )


def test__figure_producer__requires_linked_geometry_warning(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    page = reading_evidence_fixture.page()
    source_object = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "figure"
    )
    span = ReadingSourceSpanEvidence(
        source_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE, "book"
        ),
        page_location=page,
        source_object_id=source_object,
        geometry_warning_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.WARNING, "invalid-geometry"
        ),
    )

    with pytest.raises(ValueError, match="absent from warning_ids"):
        reading_evidence_fixture.producer_lineage(
            source_object_id=source_object,
            page=page,
            source_spans=ReadingSourceSpanEvidenceInventory(span),
            warning_ids=ReadingEvidenceIdentityInventory(
                ReadingEvidenceIdentityKind.WARNING
            ),
        )


def test__equation_producer__enforces_recognition_and_gate_state(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    page = reading_evidence_fixture.page()
    source_object = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "equation"
    )
    record = ReadingEquationProducerEvidence(
        assembly_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.ASSEMBLY, "equation"
        ),
        candidate_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.CANDIDATE, "equation"
        ),
        lineage=reading_evidence_fixture.producer_lineage(
            source_object_id=source_object,
            page=page,
            producer_token="equation",
        ),
        native_representation="E = mc^2",
        recognized_representation=None,
        selection_disposition=ReadingEquationSelectionDisposition.AUXILIARY,
        recognition_status=ReadingEquationRecognitionStatus.NOT_REQUESTED,
        gate=ReadingEquationGate(
            review_status=ReadingReviewStatus.UNREVIEWED,
            accepted=False,
            review_required=True,
            chunk_text_eligible=False,
        ),
    )

    assert len(ReadingEquationProducerEvidenceInventory(record)) == 1
    assert not record.gate.chunk_text_eligible

    with pytest.raises(ValueError, match="unreviewed"):
        ReadingEquationGate(
            review_status=ReadingReviewStatus.UNREVIEWED,
            accepted=False,
            review_required=True,
            chunk_text_eligible=True,
        )


def test__equation_producer__requires_recognized_text_on_success(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    source_object = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.SOURCE_OBJECT, "equation"
    )

    with pytest.raises(ValueError, match="conflicts"):
        ReadingEquationProducerEvidence(
            assembly_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.ASSEMBLY, "equation"
            ),
            candidate_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.CANDIDATE, "equation"
            ),
            lineage=reading_evidence_fixture.producer_lineage(
                source_object_id=source_object,
                producer_token="equation",
            ),
            native_representation="E = mc^2",
            recognized_representation=None,
            selection_disposition=ReadingEquationSelectionDisposition.PRIMARY,
            recognition_status=ReadingEquationRecognitionStatus.SUCCEEDED,
            gate=ReadingEquationGate(
                review_status=ReadingReviewStatus.ACCEPTED,
                accepted=True,
                review_required=False,
                chunk_text_eligible=True,
            ),
        )
