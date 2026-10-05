from __future__ import annotations

import pytest
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.actionizer import (  # noqa: E501
    ExtractionProjectionInventoryActionizer,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.reader import (  # noqa: E501
    ExtractionProjectionInventoryReader,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.reader_error import (  # noqa: E501
    ExtractionProjectionInventoryReaderError,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.request import (  # noqa: E501
    ExtractionProjectionInventoryRequest,
)


class InventoryReader(ExtractionProjectionInventoryReader):
    def __init__(
        self,
        error: ExtractionProjectionInventoryReaderError | None = None,
    ) -> None:
        self.error = error

    def read_inventory(
        self,
        *,
        projection_reference: str,
        authority_id: str,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        assert projection_reference == "projection:fixture"
        assert authority_id == "authority:fixture"
        if self.error is not None:
            raise self.error
        return tuple(
            ExtractionProjectionCollectionInventory.create(
                collection_name=name,
                members=(),
            )
            for name in ExtractionProjectionInventoryActionizer.collection_names
        )


def test__projection_inventory_action__is_stable_and_compact() -> None:
    request = ExtractionProjectionInventoryRequest.create(
        projection_reference="projection:fixture",
        authority_id="authority:fixture",
    )
    actionizer = ExtractionProjectionInventoryActionizer(
        reader=InventoryReader()
    )

    first = actionizer.action(request=request)
    second = actionizer.action(request=request)

    assert first == second
    assert first.status is ExtractionActionStatus.COMPLETED
    assert first.disposition is ExtractionActionDisposition.CONTINUE
    assert [item.document_count for item in first.collections] == [0] * 5
    assert not hasattr(first.collections[0], "members")


def test__projection_inventory_request__authority_is_not_idempotency() -> None:
    first = ExtractionProjectionInventoryRequest.create(
        projection_reference="projection:fixture",
        authority_id="authority:fixture",
    )
    second = ExtractionProjectionInventoryRequest.create(
        projection_reference="projection:fixture",
        authority_id="authority:replacement",
    )

    assert first.request_id != second.request_id
    assert first.idempotency_key == second.idempotency_key


def test__projection_inventory_action__preserves_query_disposition() -> None:
    request = ExtractionProjectionInventoryRequest.create(
        projection_reference="projection:fixture",
        authority_id="authority:fixture",
    )
    error = ExtractionProjectionInventoryReaderError(
        code="projection_temporarily_unavailable",
        disposition=ExtractionActionDisposition.RETRY_SAME_REQUEST,
        message="projection is temporarily unavailable",
    )

    result = ExtractionProjectionInventoryActionizer(
        reader=InventoryReader(error)
    ).action(request=request)

    assert result.status is ExtractionActionStatus.FAILED
    assert result.disposition is ExtractionActionDisposition.RETRY_SAME_REQUEST
    assert result.failure_code == "projection_temporarily_unavailable"


def test__collection_inventory__rejects_duplicate_identity() -> None:
    digest = "0" * 64

    with pytest.raises(ValueError, match="must be unique"):
        ExtractionProjectionCollectionInventory.create(
            collection_name="extraction_documents",
            members=(("document:1", digest), ("document:1", digest)),
        )
