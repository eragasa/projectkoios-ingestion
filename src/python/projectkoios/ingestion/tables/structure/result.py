"""TableStructureResult table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import IngestionWarning
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)
from projectkoios.ingestion.tables.structure.structure import TableStructure
from projectkoios.ingestion.tables.structure.validation import (
    TableStructureValidation,
)


@dataclass(frozen=True)
class TableStructureResult(
    AbstractTableStructureDataObject, DataObjectActionResult
):
    result_id: str
    structure_input: TableStructureRequest
    structures: tuple[TableStructure, ...]
    warnings: tuple[IngestionWarning, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input: TableStructureRequest,
        structures: tuple[TableStructure, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> TableStructureResult:
        TableStructureValidation._preflight_result(
            structure_input,
            structures,
            warnings,
            processor_name,
            processor_version,
        )
        digest = structure_input.configuration.configuration_digest
        TableStructureValidation._validate_retained_size(
            (
                structure_input,
                structures,
                warnings,
                processor_name,
                processor_version,
            ),
            structure_input.configuration.max_result_bytes,
        )
        return cls(
            result_id=cls._derived_id(
                structure_input.input_id,
                structures,
                warnings,
                processor_name,
                processor_version,
                digest,
            ),
            structure_input=structure_input,
            structures=structures,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table structure-result version")
        TableStructureValidation._preflight_result(
            self.structure_input,
            self.structures,
            self.warnings,
            self.processor_name,
            self.processor_version,
        )
        TableStructureValidation.create(result=self)
        if self.result_id != self._derived_id(
            self.structure_input.input_id,
            self.structures,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table structure-result ID is inconsistent")

    @staticmethod
    def _derived_id(
        input_id: str,
        structures: tuple[TableStructure, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> str:
        return stable_id(
            "table-structure-result",
            input_id,
            tuple(
                (
                    structure.structure_id,
                    structure.warning_ids,
                    tuple(
                        (cell.cell_id, cell.warning_ids)
                        for cell in structure.cells
                    ),
                )
                for structure in structures
            ),
            tuple(
                (
                    warning.warning_id,
                    warning.code,
                    warning.object_ids,
                    tuple(
                        span.identity_parts() for span in warning.source_spans
                    ),
                    warning.evidence,
                )
                for warning in warnings
            ),
            processor_name,
            processor_version,
            configuration_digest,
        )

    @property
    def request(self) -> TableStructureRequest:
        """Return the exact request retained by this result."""
        return self.structure_input

    @property
    def request_id(self) -> str:
        return self.structure_input.request_id

    @property
    def actionizer_name(self) -> str:
        return self.processor_name

    @property
    def actionizer_version(self) -> str:
        return self.processor_version
