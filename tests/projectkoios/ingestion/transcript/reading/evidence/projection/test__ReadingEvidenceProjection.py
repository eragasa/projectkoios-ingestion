from dataclasses import replace

import pytest
from projectkoios.base import DataObjectActionizer, DataObjectActionResult
from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
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
from projectkoios.ingestion.transcript.reading.evidence.input.text.inventory import (  # noqa: E501
    ReadingCleanTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.expected import (  # noqa: E501
    ExpectedReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.code import (
    ReadingEvidenceLimitationCode,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.actionizer import (  # noqa: E501
    ReadingEvidenceProjectionActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.identity import (  # noqa: E501
    ReadingEvidenceProjectionIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.limitation import (  # noqa: E501
    derive_reading_evidence_limitations,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.page import (
    project_reading_evidence_pages,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.result import (  # noqa: E501
    ReadingEvidenceProjectionResult,
)

from .fixture import ReadingEvidenceProjectionFixture
from .visual_fixture import ReadingVisualProjectionFixture


def test__projection__constructs_one_deterministic_canonical_document() -> None:
    fixture = ReadingEvidenceProjectionFixture.build()
    actionizer = ReadingEvidenceProjectionActionizer()

    first = actionizer.action(request=fixture.request)
    second = actionizer.action(request=fixture.request)

    assert isinstance(actionizer, DataObjectActionizer)
    assert isinstance(first, DataObjectActionResult)
    assert isinstance(first, ReadingEvidenceProjectionResult)
    assert first == second
    assert first.reconciliation.complete
    assert first.inventory.measures.page_count == 1
    assert first.inventory.measures.paragraph_count == 1
    page = next(iter(first.document.pages))
    block = next(iter(page.blocks))
    assert block.kind is ReadingEvidenceBlockKind.PARAGRAPH
    assert block.text == "Canonical paragraph."


def test__projection__selects_exact_caption_and_retains_limitation() -> None:
    fixture = ReadingVisualProjectionFixture.build()

    result = ReadingEvidenceProjectionActionizer().action(
        request=fixture.request
    )

    page = next(iter(result.document.pages))
    figure = tuple(page.blocks)[1]
    assert type(figure) is ReadingFigureEvidenceBlock
    assert figure.caption is not None
    assert figure.caption.text == "Figure title"
    assert result.inventory.measures.figure_count == 1
    assert result.inventory.measures.caption_count == 1
    assert result.inventory.measures.limitation_count == 1


def test__page_projection__rejects_duplicate_clean_text_use() -> None:
    fixture = ReadingEvidenceProjectionFixture.build()
    item = tuple(fixture.request.structured_items)[0]
    duplicate = ReadingStructuredItemProducerEvidence(
        page_location=item.page_location,
        order_index=1,
        kind=item.kind,
        source_block_ids=item.source_block_ids,
        source_object_id=None,
        producer_id=item.producer_id,
        producer_version=item.producer_version,
    )
    request = replace(
        fixture.request,
        structured_items=ReadingStructuredItemProducerEvidenceInventory(
            item,
            duplicate,
        ),
    )

    with pytest.raises(ReadingEvidenceError, match="multiply used"):
        project_reading_evidence_pages(request=request)


def test__page_projection__rejects_duplicate_visual_producer_use() -> None:
    fixture = ReadingVisualProjectionFixture.build()
    paragraph, figure = tuple(fixture.request.structured_items)
    duplicate = ReadingStructuredItemProducerEvidence(
        page_location=figure.page_location,
        order_index=2,
        kind=figure.kind,
        source_block_ids=figure.source_block_ids,
        source_object_id=figure.source_object_id,
        producer_id=figure.producer_id,
        producer_version=figure.producer_version,
    )
    request = replace(
        fixture.request,
        structured_items=ReadingStructuredItemProducerEvidenceInventory(
            paragraph,
            figure,
            duplicate,
        ),
    )

    with pytest.raises(ReadingEvidenceError, match="multiply used"):
        project_reading_evidence_pages(request=request)


def test__limitation_derivation__retains_unplaced_producer_evidence() -> None:
    fixture = ReadingVisualProjectionFixture.build()
    paragraph = tuple(fixture.request.structured_items)[0]
    request = replace(
        fixture.request,
        structured_items=ReadingStructuredItemProducerEvidenceInventory(
            paragraph
        ),
    )

    page_projection = project_reading_evidence_pages(request=request)
    limitations = derive_reading_evidence_limitations(
        request=request,
        page_projection=page_projection,
    )

    unplaced = next(
        value
        for value in limitations
        if value.code
        is ReadingEvidenceLimitationCode.UNPLACED_PRODUCER_EVIDENCE
    )
    assert tuple(unplaced.affected_ids) == (
        tuple(request.figures)[0].record_id,
    )


def test__request__rejects_clean_text_from_unselected_stream() -> None:
    fixture = ReadingEvidenceProjectionFixture.build()
    record = tuple(fixture.request.clean_text)[0]
    clean_text = ReadingCleanTextProducerEvidenceInventory(
        replace(
            record,
            selected_stream_id=ReadingEvidenceIdentity(
                kind=ReadingEvidenceIdentityKind.TEXT_STREAM,
                value="text-stream:other",
            ),
        )
    )

    with pytest.raises(ReadingEvidenceError, match="selected page stream"):
        replace(fixture.request, clean_text=clean_text)


def test__request__rejects_unreferenced_managed_artifact() -> None:
    fixture = ReadingEvidenceProjectionFixture.build()
    references = (
        *fixture.request.managed_artifacts,
        fixture.foundation.artifact(),
    )
    managed = ManagedArtifactReferenceInventory(
        *sorted(references, key=lambda value: value.artifact_id)
    )

    with pytest.raises(ReadingEvidenceError, match="referenced producer"):
        replace(fixture.request, managed_artifacts=managed)


def test__document__rejects_block_producer_absent_from_retained_evidence() -> (
    None
):
    fixture = ReadingVisualProjectionFixture.build()
    document = (
        ReadingEvidenceProjectionActionizer()
        .action(request=fixture.request)
        .document
    )
    source_only = ManagedArtifactReferenceInventory(
        document.producer_evidence.source_artifact
    )
    lineage = replace(
        document.lineage,
        figure_inventory_id=(
            ReadingEvidenceProjectionIdentityDerivation.derive_inventory(
                role="figures",
                identities=[],
            )
        ),
        managed_artifacts=source_only,
    )

    with pytest.raises(ReadingEvidenceError, match="absent from retained"):
        replace(
            document,
            retained_figures=ReadingFigureProducerEvidenceInventory(),
            managed_artifacts=source_only,
            lineage=lineage,
        )


def test__document__rejects_document_producer_lineage_mismatch() -> None:
    fixture = ReadingEvidenceProjectionFixture.build()
    document = (
        ReadingEvidenceProjectionActionizer()
        .action(request=fixture.request)
        .document
    )
    lineage = replace(
        document.lineage,
        extraction_result_id=ReadingEvidenceIdentity(
            kind=ReadingEvidenceIdentityKind.EXTRACTION_RESULT,
            value="extraction-result:other",
        ),
    )

    with pytest.raises(ReadingEvidenceError, match="producer evidence"):
        replace(document, lineage=lineage)


def test__request__rejects_producer_lineage_from_another_source() -> None:
    fixture = ReadingEvidenceProjectionFixture.build()
    document = replace(
        fixture.request.document,
        source_id=ReadingEvidenceIdentity(
            kind=ReadingEvidenceIdentityKind.SOURCE,
            value="source:other",
        ),
    )

    with pytest.raises(ReadingEvidenceError, match="source lineage"):
        replace(fixture.request, document=document)


def test__projection__rejects_independent_inventory_mismatch() -> None:
    fixture = ReadingEvidenceProjectionFixture.build()
    mismatched_measures = replace(
        fixture.request.expected_inventory.measures,
        block_count=2,
        character_count=(
            fixture.request.expected_inventory.measures.character_count + 1
        ),
    )
    request = replace(
        fixture.request,
        expected_inventory=ExpectedReadingEvidenceInventory(
            measures=mismatched_measures
        ),
    )

    with pytest.raises(
        ReadingEvidenceError,
        match="block_count, character_count",
    ):
        ReadingEvidenceProjectionActionizer().action(request=request)
