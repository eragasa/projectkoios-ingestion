"""Current structured-item and clean-text producer action tests."""

from dataclasses import replace

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    CleanTranscriptBlock,
    CleanTranscriptPage,
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
        transcription=fixture.source.transcription,
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
        assert len(record.source_spans) > 0
        assert all(
            span.page_location == record.page_location
            and span.source_id.kind is ReadingEvidenceIdentityKind.SOURCE
            for span in record.source_spans
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
            transcription=fixture.source.transcription,
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


def test__clean_text_producer__omits_invalid_geometry_with_warning(
    reading_current_producer_fixture: ReadingCurrentProducerFixture,
) -> None:
    fixture = reading_current_producer_fixture
    original = fixture.transcript
    original_block = original.blocks[0]
    source_span = original_block.source_spans[0]
    invalid_span = replace(source_span, bounding_box=(-1.0, 0.0, 1.0, 1.0))
    block = CleanTranscriptBlock.create(
        block_id=original_block.block_id,
        page_index=original_block.page_index,
        printed_page_label=original_block.printed_page_label,
        order_index=original_block.order_index,
        raw_text=original_block.raw_text,
        clean_text=original_block.clean_text,
        source_spans=(invalid_span, *original_block.source_spans[1:]),
        transformations=original_block.transformations,
        dehyphenation_decision_ids=original_block.dehyphenation_decision_ids,
        page_number_classification_id=(
            original_block.page_number_classification_id
        ),
        publisher_classification_id=(
            original_block.publisher_classification_id
        ),
        private_use_finding_ids=original_block.private_use_finding_ids,
    )
    blocks = (block, *original.blocks[1:])
    pages = tuple(
        CleanTranscriptPage.create(
            page_index=page.page_index,
            printed_page_label=page.printed_page_label,
            block_record_ids=tuple(
                block.record_id
                if record_id == original_block.record_id
                else record_id
                for record_id in page.block_record_ids
            ),
            text=page.text,
        )
        for page in original.pages
    )
    transcript = CleanTranscript.create(
        transcription_result=fixture.source.transcription,
        layouts=fixture.source.layouts,
        pages=pages,
        blocks=blocks,
        exclusions=original.exclusions,
        dehyphenation_decisions=original.dehyphenation_decisions,
        page_number_classifications=original.page_number_classifications,
        publisher_front_matter=original.publisher_front_matter,
        private_use_glyph_findings=original.private_use_glyph_findings,
        text=original.text,
        warnings=original.warnings,
        processor_name=original.processor_name,
        processor_version=original.processor_version,
        configuration_digest=original.configuration_digest,
    )

    result = ReadingCleanTextProducerActionizer().action(
        request=ReadingCleanTextProductionRequest(
            transcript=transcript,
            transcription=fixture.source.transcription,
            page_text=fixture.page_text,
        )
    )

    projected = tuple(result.evidence)[0]
    projected_span = tuple(projected.source_spans)[0]
    assert projected_span.bounding_box is None
    assert projected_span.geometry_warning_id is not None
    assert projected_span.geometry_warning_id in projected.warning_ids


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
            transcription=fixture.source.transcription,
            page_text=partial,
        )
