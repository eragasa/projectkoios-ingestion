"""TableColumn table-structure domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)


@dataclass(frozen=True)
class TableColumn(AbstractTableStructureDataObject):
    column_id: str
    structure_input_id: str
    candidate_id: str
    column_index: int
    normalized_left: float
    normalized_right: float
    source_region_ids: tuple[str, ...]
    confidence: float
    evidence: Metadata
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = TABLE_STRUCTURE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        structure_input_id: str,
        candidate_id: str,
        column_index: int,
        normalized_left: float,
        normalized_right: float,
        source_region_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableColumn:
        left, right, normalized_confidence = cls._validated_parts(
            structure_input_id,
            candidate_id,
            column_index,
            normalized_left,
            normalized_right,
            source_region_ids,
            confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        column_id = cls._derived_id(
            structure_input_id,
            candidate_id,
            column_index,
            left,
            right,
            source_region_ids,
            normalized_confidence,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            column_id=column_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            column_index=column_index,
            normalized_left=left,
            normalized_right=right,
            source_region_ids=source_region_ids,
            confidence=normalized_confidence,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table column version")
        left, right, confidence = self._validated_parts(
            self.structure_input_id,
            self.candidate_id,
            self.column_index,
            self.normalized_left,
            self.normalized_right,
            self.source_region_ids,
            self.confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "normalized_left", left)
        object.__setattr__(self, "normalized_right", right)
        object.__setattr__(self, "confidence", confidence)
        if self.column_id != self._derived_id(
            self.structure_input_id,
            self.candidate_id,
            self.column_index,
            left,
            right,
            self.source_region_ids,
            confidence,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table column ID is inconsistent")

    @classmethod
    def _validated_parts(
        cls,
        structure_input_id: str,
        candidate_id: str,
        column_index: int,
        normalized_left: float,
        normalized_right: float,
        source_region_ids: tuple[str, ...],
        confidence: float,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> tuple[float, float, float]:
        cls._validate_identity_fields(
            structure_input_id,
            candidate_id,
            processor_name,
            processor_version,
            configuration_digest,
        )
        cls._validate_nonnegative_integer("column index", column_index)
        left = cls._validate_unit_float(
            "normalized column left", normalized_left
        )
        right = cls._validate_unit_float(
            "normalized column right", normalized_right
        )
        if right <= left:
            raise ValueError(
                "normalized column bounds must have positive width"
            )
        cls._validate_unique_strings(
            "column source region IDs", source_region_ids, required=True
        )
        cls._validate_metadata(evidence)
        return (
            left,
            right,
            cls._validate_unit_float("column confidence", confidence),
        )

    @staticmethod
    def _derived_id(*values: object) -> str:
        return stable_id("table-column", *values)
