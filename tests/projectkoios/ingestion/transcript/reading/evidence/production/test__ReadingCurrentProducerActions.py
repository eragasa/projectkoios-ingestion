"""Current structured-item and clean-text producer action tests."""

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.inventory import (  # noqa: E501
    ReadingPageTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.production.actionizer import (  # noqa: E501
    ReadingStructuredItemProducerActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.production.request import (  # noqa: E501
    ReadingStructuredItemProductionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.production.result import (  # noqa: E501
    ReadingStructuredItemProductionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.production.actionizer import (  # noqa: E501
    ReadingCleanTextProducerActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.production.request import (  # noqa: E501
    ReadingCleanTextProductionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.production.result import (  # noqa: E501
    ReadingCleanTextProductionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.kind import (  # noqa: E501
    ReadingTextTransformationKind,
)
from projectkoios.ingestion.transcription.kind.item import TranscriptionItemKind

from tests.projectkoios.ingestion.transcript.reading.evidence.production.fixture import (  # noqa: E501
    ReadingCurrentProducerFixture,
)


def test__structured_item_producer__is_one_pure_action(
    reading_current_producer_fixture: ReadingCurrentProducerFixture,
) -> None:
    fixture = reading_current_producer_fixture
    request = ReadingStructuredItemProductionRequest(
        transcription=fixture.source.transcription,
        page_text=fixture.page_text,
    )
    actionizer = ReadingStructuredItemProducerActionizer()

    first = actionizer.action(request=request)
    second = actionizer.action(request=request)

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(actionizer, DataObjectActionizer)
    assert isinstance(first, DataObjectActionResult)
    assert isinstance(first, ReadingStructuredItemProductionResult)
    assert first == second
    assert first.source_result_id.kind is (
        ReadingEvidenceIdentityKind.STRUCTURED_TRANSCRIPTION
    )
    expected_count = sum(
        item.item_kind is not TranscriptionItemKind.PAGE_ANCHOR
        for item in fixture.source.transcription.items
    )
    assert len(first.evidence) == expected_count
    assert all(
        item.kind
        in {
            ReadingStructuredItemKind.PARAGRAPH,
            ReadingStructuredItemKind.HEADING,
            ReadingStructuredItemKind.FIGURE,
            ReadingStructuredItemKind.TABLE,
            ReadingStructuredItemKind.EQUATION,
        }
        for item in first.evidence
    )
    for page_index in range(len(fixture.page_text)):
        assert [
            item.order_index
            for item in first.evidence
            if item.page_location.physical_page_index == page_index
        ] == list(
            range(
                sum(
                    item.page_location.physical_page_index == page_index
                    for item in first.evidence
                )
            )
        )


def test__clean_text_producer__binds_selected_stream_and_exact_replay(
    reading_current_producer_fixture: ReadingCurrentProducerFixture,
) -> None:
    fixture = reading_current_producer_fixture
    request = ReadingCleanTextProductionRequest(
        transcript=fixture.transcript,
        page_text=fixture.page_text,
    )
    actionizer = ReadingCleanTextProducerActionizer()

    first = actionizer.action(request=request)
    second = actionizer.action(request=request)

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(actionizer, DataObjectActionizer)
    assert isinstance(first, DataObjectActionResult)
    assert isinstance(first, ReadingCleanTextProductionResult)
    assert first == second
    assert (
        first.source_result_id.kind
        is ReadingEvidenceIdentityKind.CLEAN_TRANSCRIPT
    )
    assert len(first.evidence) == len(fixture.transcript.blocks)
    pages = tuple(fixture.page_text)
    transformation_kinds = set()
    for record in first.evidence:
        page = pages[record.page_location.physical_page_index]
        assert record.selected_stream_id == page.selection.selected_stream_id
        assert (
            record.transformations.apply(record.raw_text) == record.clean_text
        )
        transformation_kinds.update(
            value.kind for value in record.transformations
        )
    assert ReadingTextTransformationKind.DEHYPHENATION in transformation_kinds


def test__clean_text_producer__types_sanitation_and_whitespace_edits() -> None:
    fixture = ReadingCurrentProducerFixture.build(
        replacement_split=" \x00co\u00ad operate \n"
    )

    result = ReadingCleanTextProducerActionizer().action(
        request=ReadingCleanTextProductionRequest(
            transcript=fixture.transcript,
            page_text=fixture.page_text,
        )
    )

    transformations = tuple(
        transformation
        for record in result.evidence
        for transformation in record.transformations
    )
    kinds = {value.kind for value in transformations}
    assert ReadingTextTransformationKind.GLYPH_SUBSTITUTION in kinds
    assert ReadingTextTransformationKind.WHITESPACE_NORMALIZATION in kinds
    assert all(
        record.transformations.apply(record.raw_text) == record.clean_text
        for record in result.evidence
    )


def test__current_producer_requests__reject_partial_page_binding(
    reading_current_producer_fixture: ReadingCurrentProducerFixture,
) -> None:
    fixture = reading_current_producer_fixture
    pages = tuple(fixture.page_text)
    partial = ReadingPageTextProducerEvidenceInventory(*pages[:-1])

    with pytest.raises(ReadingEvidenceError, match="equal coverage"):
        ReadingStructuredItemProductionRequest(
            transcription=fixture.source.transcription,
            page_text=partial,
        )
    with pytest.raises(ReadingEvidenceError, match="equal coverage"):
        ReadingCleanTextProductionRequest(
            transcript=fixture.transcript,
            page_text=partial,
        )
