"""DeterministicTableStructureReconstructor table-structure domain object."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.tables.contracts import TableDetectionResult
from projectkoios.ingestion.tables.structure.configuration import (
    TableStructureConfiguration,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_RECONSTRUCTOR_VERSION,
)
from projectkoios.ingestion.tables.structure.derivation import (
    TableStructureDerivation,
)
from projectkoios.ingestion.tables.structure.reconstruction import (
    TableStructureReconstructor,
)
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)
from projectkoios.ingestion.tables.structure.result import TableStructureResult


class DeterministicTableStructureReconstructor(
    DataObjectActionizer[TableStructureRequest, TableStructureResult],
    TableStructureReconstructor,
):
    """Propose bounded rows, columns, cells, spans, and continuations."""

    __slots__ = ("configuration",)

    name = "deterministic-table-structure-reconstructor"
    version = TABLE_STRUCTURE_RECONSTRUCTOR_VERSION

    def __init__(
        self, configuration: TableStructureConfiguration | None = None
    ) -> None:
        self.configuration = configuration or TableStructureConfiguration()

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def reconstruct(
        self, detection_result: TableDetectionResult
    ) -> TableStructureResult:
        request = TableStructureRequest.create(
            detection_result=detection_result,
            configuration=self.configuration,
        )
        return self.action(request=request)

    def action(self, *, request: TableStructureRequest) -> TableStructureResult:
        """Return the proposed structure for one complete request."""
        if not isinstance(request, TableStructureRequest):
            raise TypeError("request must be TableStructureRequest")
        structure_input = request
        derivations = tuple(
            TableStructureDerivation.create(
                structure_input=structure_input,
                candidate=candidate,
                processor_name=self.name,
                processor_version=self.version,
            )
            for candidate in request.detection_result.candidates
        )
        return TableStructureResult.from_derivations(
            structure_input=structure_input,
            derivations=derivations,
            processor_name=self.name,
            processor_version=self.version,
        )
