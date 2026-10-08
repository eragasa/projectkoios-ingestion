from dataclasses import replace

import pytest
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
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
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.inventory import (  # noqa: E501
    ReadingCleanTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.definition import (  # noqa: E501
    ReadingTextTransformation,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.inventory import (  # noqa: E501
    ReadingTextTransformationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.kind import (  # noqa: E501
    ReadingTextTransformationKind,
)

from .fixture import ReadingEvidenceFoundationFixture


def test__clean_text_producer__binds_text_digests_and_transformations(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    raw_text = "effec-\ntive"
    transformation = ReadingTextTransformation(
        kind=ReadingTextTransformationKind.DEHYPHENATION,
        source_start_offset=0,
        source_end_offset=len(raw_text),
        replacement_text="effective",
        rule_id="line-break-hyphen-v1",
    )
    stream = next(iter(reading_evidence_fixture.native_streams()))
    record = ReadingCleanTextProducerEvidence(
        selected_stream_id=stream.stream_id,
        source_block_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE_BLOCK, "paragraph"
        ),
        page_location=stream.page_location,
        order_index=0,
        raw_text=raw_text,
        clean_text="effective",
        transformations=ReadingTextTransformationInventory(transformation),
        producer_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "clean"
        ),
        producer_version="1",
    )

    assert record.raw_text_sha256 != record.clean_text_sha256
    assert len(ReadingCleanTextProducerEvidenceInventory(record)) == 1
    with pytest.raises(ValueError, match="does not match"):
        replace(record, clean_text="changed")


def test__clean_text_inventory__requires_contiguous_page_order(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    stream = next(iter(reading_evidence_fixture.native_streams()))
    record = ReadingCleanTextProducerEvidence(
        selected_stream_id=stream.stream_id,
        source_block_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE_BLOCK, "paragraph"
        ),
        page_location=stream.page_location,
        order_index=1,
        raw_text="text",
        clean_text="text",
        transformations=ReadingTextTransformationInventory(),
        producer_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "clean"
        ),
        producer_version="1",
    )

    with pytest.raises(ValueError, match="contiguous"):
        ReadingCleanTextProducerEvidenceInventory(record)


def test__text_transformation_inventory__rejects_overlap() -> None:
    first = ReadingTextTransformation(
        kind=ReadingTextTransformationKind.WHITESPACE_NORMALIZATION,
        source_start_offset=0,
        source_end_offset=3,
        replacement_text=" ",
        rule_id="space-v1",
    )
    second = ReadingTextTransformation(
        kind=ReadingTextTransformationKind.GLYPH_SUBSTITUTION,
        source_start_offset=2,
        source_end_offset=4,
        replacement_text="x",
        rule_id="glyph-v1",
    )

    with pytest.raises(ValueError, match="must not overlap"):
        ReadingTextTransformationInventory(first, second)


def test__clean_text_producer__requires_exact_transformation_replay(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    stream = next(iter(reading_evidence_fixture.native_streams()))

    with pytest.raises(ValueError, match="does not match"):
        ReadingCleanTextProducerEvidence(
            selected_stream_id=stream.stream_id,
            source_block_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.SOURCE_BLOCK, "paragraph"
            ),
            page_location=stream.page_location,
            order_index=0,
            raw_text="raw",
            clean_text="clean",
            transformations=ReadingTextTransformationInventory(),
            producer_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "clean"
            ),
            producer_version="1",
        )


def test__clean_text_producer__rejects_out_of_range_transformation(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    transformation = ReadingTextTransformation(
        kind=ReadingTextTransformationKind.GLYPH_SUBSTITUTION,
        source_start_offset=0,
        source_end_offset=100,
        replacement_text="x",
        rule_id="glyph-v1",
    )
    stream = next(iter(reading_evidence_fixture.native_streams()))

    with pytest.raises(ValueError, match="exceeds source text"):
        ReadingCleanTextProducerEvidence(
            selected_stream_id=stream.stream_id,
            source_block_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.SOURCE_BLOCK, "paragraph"
            ),
            page_location=stream.page_location,
            order_index=0,
            raw_text="x",
            clean_text="x",
            transformations=ReadingTextTransformationInventory(transformation),
            producer_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "clean"
            ),
            producer_version="1",
        )


def test__structured_item__separates_text_and_visual_join_keys(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    page = reading_evidence_fixture.page()
    block_ids = ReadingEvidenceIdentityInventory(
        ReadingEvidenceIdentityKind.SOURCE_BLOCK,
        reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE_BLOCK, "paragraph"
        ),
    )
    producer_id = reading_evidence_fixture.identity(
        ReadingEvidenceIdentityKind.PRODUCER, "structure"
    )
    paragraph = ReadingStructuredItemProducerEvidence(
        page_location=page,
        order_index=0,
        kind=ReadingStructuredItemKind.PARAGRAPH,
        source_block_ids=block_ids,
        source_object_id=None,
        producer_id=producer_id,
        producer_version="1",
    )
    figure = ReadingStructuredItemProducerEvidence(
        page_location=page,
        order_index=1,
        kind=ReadingStructuredItemKind.FIGURE,
        source_block_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.SOURCE_BLOCK
        ),
        source_object_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE_OBJECT, "figure"
        ),
        producer_id=producer_id,
        producer_version="1",
    )

    inventory = ReadingStructuredItemProducerEvidenceInventory(
        paragraph,
        figure,
    )

    assert len(inventory) == 2
    with pytest.raises(ValueError, match="visual item requires"):
        ReadingStructuredItemProducerEvidence(
            page_location=page,
            order_index=2,
            kind=ReadingStructuredItemKind.TABLE,
            source_block_ids=block_ids,
            source_object_id=reading_evidence_fixture.identity(
                ReadingEvidenceIdentityKind.SOURCE_OBJECT, "table"
            ),
            producer_id=producer_id,
            producer_version="1",
        )


def test__structured_item_inventory__requires_contiguous_page_order(
    reading_evidence_fixture: ReadingEvidenceFoundationFixture,
) -> None:
    item = ReadingStructuredItemProducerEvidence(
        page_location=reading_evidence_fixture.page(),
        order_index=1,
        kind=ReadingStructuredItemKind.FIGURE,
        source_block_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.SOURCE_BLOCK
        ),
        source_object_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.SOURCE_OBJECT, "figure"
        ),
        producer_id=reading_evidence_fixture.identity(
            ReadingEvidenceIdentityKind.PRODUCER, "structure"
        ),
        producer_version="1",
    )

    with pytest.raises(ValueError, match="contiguous"):
        ReadingStructuredItemProducerEvidenceInventory(item)
