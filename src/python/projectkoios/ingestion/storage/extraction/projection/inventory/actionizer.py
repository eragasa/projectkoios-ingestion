"""Provider actionizer for extraction projector inventories."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.base.inventory.identity.error import (
    InventoryIdentityError,
)
from projectkoios.ingestion.base.inventory.request import InventoryRequest
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.inventory import (  # noqa: E501
    ExtractionProjectorInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.reader import (  # noqa: E501
    ExtractionProjectionInventoryReader,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.reader_error import (  # noqa: E501
    ExtractionProjectionInventoryReaderError,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.request import (  # noqa: E501
    ExtractionProjectionInventoryRequest,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.result import (  # noqa: E501
    ExtractionProjectionInventoryResult,
)


class ExtractionProjectionInventoryActionizer(
    DataObjectActionizer[
        ExtractionProjectionInventoryRequest,
        ExtractionProjectionInventoryResult,
    ]
):
    """Map read-only inventory evidence and failures to provider outcomes."""

    __slots__ = ("inventory",)

    actionizer_name = "extraction-projection-inventory"
    actionizer_version = "2"
    collection_names = (
        ExtractionProjectionInventoryConfiguration.mongodb_v1().collection_names
    )

    def __init__(self, *, reader: ExtractionProjectionInventoryReader) -> None:
        self.inventory = ExtractionProjectorInventory(reader=reader)

    def action(
        self,
        *,
        request: ExtractionProjectionInventoryRequest,
    ) -> ExtractionProjectionInventoryResult:
        if type(request) is not ExtractionProjectionInventoryRequest:
            raise TypeError(
                "request must be an ExtractionProjectionInventoryRequest"
            )
        generic = InventoryRequest.create(
            target=request.target,
            configuration=request.configuration,
            authority_id=request.authority_id,
        )
        try:
            evidence = self.inventory.action(request=generic).evidence
        except ExtractionProjectionInventoryReaderError as error:
            return ExtractionProjectionInventoryResult.failed(
                request=request,
                disposition=error.disposition,
                failure_code=error.code,
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        except InventoryIdentityError:
            return ExtractionProjectionInventoryResult.failed(
                request=request,
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                failure_code="projection_inventory_identity_differs",
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        return ExtractionProjectionInventoryResult.completed(
            request=request,
            collections=evidence.collections,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
