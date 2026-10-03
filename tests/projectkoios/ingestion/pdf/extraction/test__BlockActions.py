from __future__ import annotations

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion.pdf.extraction.geometry import (
    BlockGeometryActionizer,
    BlockGeometryRequest,
)
from projectkoios.ingestion.pdf.extraction.text import (
    MAXIMUM_BLOCK_TEXT_LINES,
    BlockTextActionizer,
    BlockTextLimitError,
    BlockTextRequest,
)


def test__block_geometry_validation_is_a_data_object_action() -> None:
    request = BlockGeometryRequest.create(
        coordinates=(10.0, 20.0, 30.0, 40.0),
        coordinate_count=4,
    )
    actionizer = BlockGeometryActionizer()

    result = actionizer.action(request=request)

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(actionizer, DataObjectActionizer)
    assert isinstance(result, DataObjectActionResult)
    assert result.request_id == request.request_id
    assert result.bounding_box == (10.0, 20.0, 30.0, 40.0)
    assert result.invalid_reason is None
    assert result.actionizer_name == (
        "deterministic-pdf-block-geometry-actionizer"
    )
    assert result.actionizer_version == "1"
    assert actionizer.action(request=request) == result


def test__block_text_composition_is_a_data_object_action() -> None:
    request = BlockTextRequest.create(
        lines=(("First ", "line   "), (), ("Second line",))
    )
    actionizer = BlockTextActionizer()

    result = actionizer.action(request=request)

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(actionizer, DataObjectActionizer)
    assert isinstance(result, DataObjectActionResult)
    assert result.request_id == request.request_id
    assert result.text == "First line\nSecond line"
    assert result.actionizer_name == "deterministic-pdf-block-text-actionizer"
    assert result.actionizer_version == "1"
    assert actionizer.action(request=request) == result


def test__block_text_request__rejects_unbounded_line_evidence() -> None:
    with pytest.raises(BlockTextLimitError, match="lines"):
        BlockTextRequest.create(lines=((),) * (MAXIMUM_BLOCK_TEXT_LINES + 1))
