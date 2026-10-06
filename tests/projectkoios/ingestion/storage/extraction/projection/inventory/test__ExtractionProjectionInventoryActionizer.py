from __future__ import annotations

import pytest
from projectkoios.ingestion.base.inventory.actionizer import Inventory
from projectkoios.ingestion.base.projector.inventory.observer import (
    ProjectorInventory,
)
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.actions.status import (
    ExtractionActionStatus,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.actionizer import (  # noqa: E501
    ExtractionProjectionInventoryActionizer,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.reader.base import (  # noqa: E501
    ExtractionProjectionInventoryReader,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.reader.error import (  # noqa: E501
    ExtractionProjectionInventoryReaderError,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.request import (  # noqa: E501
    ExtractionProjectionInventoryRequest,
)


def _target() -> ExtractionProjectionTargetIdentity:
    return ExtractionProjectionTargetIdentity.create(
        deployment_id="fixture-mongodb",
        environment="test",
        database_name="fixture_database",
        schema_id="extraction-read-model-v1",
        projection_slot="extraction-publications",
    )


def _configuration() -> ExtractionProjectionInventoryConfiguration:
    return ExtractionProjectionInventoryConfiguration.mongodb_v1()


def _request(
    authority_id: str = "authority:fixture",
) -> ExtractionProjectionInventoryRequest:
    return ExtractionProjectionInventoryRequest.create(
        target=_target(),
        configuration=_configuration(),
        authority_id=authority_id,
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
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionInventoryConfiguration,
        authority_id: str,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        assert target == _target()
        assert configuration == _configuration()
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


def test__projector_inventory__inherits_inventory_pattern() -> None:
    assert issubclass(ProjectorInventory, Inventory)


def test__projection_inventory_action__is_stable_and_compact() -> None:
    request = _request()
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
    first = _request()
    second = _request("authority:replacement")

    assert first.request_id != second.request_id
    assert first.idempotency_key == second.idempotency_key


def test__projection_inventory_action__preserves_query_disposition() -> None:
    request = _request()
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
