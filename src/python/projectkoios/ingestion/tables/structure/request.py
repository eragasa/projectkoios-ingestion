"""TableStructureRequest table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.tables.contracts import (
    TABLE_CONTRACT_VERSION,
    TableDetectionResult,
)
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.configuration import (
    TableStructureConfiguration,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.validation.structure import (
    TableStructureValidation,
)


@dataclass(frozen=True)
class TableStructureRequest(
    AbstractTableStructureDataObject, DataObjectActionRequest
):
    input_id: str
    detection_result: TableDetectionResult
    configuration: TableStructureConfiguration
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_result: TableDetectionResult,
        configuration: TableStructureConfiguration | None = None,
    ) -> TableStructureRequest:
        actual = configuration or TableStructureConfiguration()
        TableStructureValidation._validate_input_parts(detection_result, actual)
        return cls(
            input_id=cls._derived_id(detection_result, actual),
            detection_result=detection_result,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table structure-input version")
        TableStructureValidation._validate_input_parts(
            self.detection_result, self.configuration
        )
        if self.input_id != self._derived_id(
            self.detection_result, self.configuration
        ):
            raise ValueError("table structure-input ID is inconsistent")

    @staticmethod
    def _derived_id(
        detection_result: TableDetectionResult,
        configuration: TableStructureConfiguration,
    ) -> str:
        return stable_id(
            "table-structure-input",
            TABLE_STRUCTURE_CONTRACT_VERSION,
            TABLE_CONTRACT_VERSION,
            detection_result.result_id,
            tuple(
                (candidate.candidate_id, candidate.warning_ids)
                for candidate in detection_result.candidates
            ),
            configuration.identity_parts(),
        )

    @property
    def request_id(self) -> str:
        """Return the established input identity as the request identity."""
        return self.input_id
