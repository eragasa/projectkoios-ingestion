"""Ownership, geometry, and immutability checks for table source records."""

from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    SourceSpan,
)
from projectkoios.ingestion.tables.structure.record.source import (
    TableSourceRecord,
)


@pytest.mark.parametrize(
    ("source_geometry", "source_order", "expected_center"),
    (
        ((10.0, 20.0, 110.0, 60.0), 0, (60.0, 40.0)),
        ((-15.0, 5.0, 45.0, 25.0), 7, (15.0, 15.0)),
    ),
)
def test__record_derives_frozen_source_geometry(
    source_geometry: BoundingBox,
    source_order: int,
    expected_center: tuple[float, float],
) -> None:
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(
            SourceSpan(
                source_id="source",
                source_blob_id="blob",
                page_index=0,
                source_object_id="block",
                bounding_box=source_geometry,
            ),
        ),
        extraction_method="fixture",
        confidence=1.0,
        text="cell",
    )

    record = TableSourceRecord.from_block(block, order=source_order)

    assert record.box == source_geometry
    assert (record.center_x, record.center_y) == expected_center
    assert record.order == source_order
    assert TableSourceRecord.__module__ == (
        "projectkoios.ingestion.tables.structure.record.source"
    )
    assert issubclass(TableSourceRecord, AbstractImmutableDataObject)
    with pytest.raises(FrozenInstanceError):
        record.order = source_order + 1  # type: ignore[misc]
