"""TableStructureResult table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass, replace

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import IngestionWarning, WarningSeverity
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.derivation.structure import (
    TableStructureDerivation,
)
from projectkoios.ingestion.tables.structure.model import TableStructure
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)
from projectkoios.ingestion.tables.structure.validation.structure import (
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
    def from_derivations(
        cls,
        *,
        structure_input: TableStructureRequest,
        derivations: tuple[TableStructureDerivation, ...],
        processor_name: str,
        processor_version: str,
    ) -> TableStructureResult:
        if not isinstance(derivations, tuple) or any(
            not isinstance(item, TableStructureDerivation)
            for item in derivations
        ):
            raise TypeError(
                "table structure derivations must be an immutable tuple"
            )
        structures, warnings = cls._link_warnings(derivations)
        return cls.create(
            structure_input=structure_input,
            structures=structures,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
        )

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

    @staticmethod
    def _link_warnings(
        derivations: tuple[TableStructureDerivation, ...],
    ) -> tuple[tuple[TableStructure, ...], tuple[IngestionWarning, ...]]:
        warnings: list[IngestionWarning] = []
        warning_ids_by_object: dict[str, list[str]] = {}
        for derivation in derivations:
            for specification in derivation.warning_specifications:
                warning = IngestionWarning.create(
                    code=specification.code,
                    severity=WarningSeverity.WARNING,
                    message=specification.message,
                    object_ids=specification.object_ids,
                    source_spans=specification.source_spans,
                    evidence=specification.evidence,
                )
                warnings.append(warning)
                for object_id in warning.object_ids:
                    warning_ids_by_object.setdefault(object_id, []).append(
                        warning.warning_id
                    )
        structures = tuple(
            replace(
                derivation.structure,
                cells=tuple(
                    replace(
                        cell,
                        warning_ids=tuple(
                            warning_ids_by_object.get(cell.cell_id, ())
                        ),
                    )
                    for cell in derivation.structure.cells
                ),
                warning_ids=tuple(
                    warning_ids_by_object.get(
                        derivation.structure.structure_id, ()
                    )
                ),
            )
            for derivation in derivations
        )
        return structures, tuple(warnings)

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
