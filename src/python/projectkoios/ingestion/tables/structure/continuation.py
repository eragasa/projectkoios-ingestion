"""TableContinuation table-structure domain object."""

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
from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)


@dataclass(frozen=True)
class TableContinuation(AbstractTableStructureDataObject):
    continuation_id: str
    structure_input_id: str
    candidate_id: str
    previous_region_id: str
    current_region_id: str
    previous_page_index: int
    current_page_index: int
    association_id: str
    confidence: float
    evidence_status: TableStructureEvidenceStatus
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
        previous_region_id: str,
        current_region_id: str,
        previous_page_index: int,
        current_page_index: int,
        association_id: str,
        confidence: float,
        evidence_status: TableStructureEvidenceStatus,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> TableContinuation:
        normalized = cls._validated_parts(
            structure_input_id,
            candidate_id,
            previous_region_id,
            current_region_id,
            previous_page_index,
            current_page_index,
            association_id,
            confidence,
            evidence_status,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        continuation_id = cls._derived_id(
            structure_input_id,
            candidate_id,
            previous_region_id,
            current_region_id,
            previous_page_index,
            current_page_index,
            association_id,
            normalized,
            evidence_status,
            evidence,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            continuation_id=continuation_id,
            structure_input_id=structure_input_id,
            candidate_id=candidate_id,
            previous_region_id=previous_region_id,
            current_region_id=current_region_id,
            previous_page_index=previous_page_index,
            current_page_index=current_page_index,
            association_id=association_id,
            confidence=normalized,
            evidence_status=evidence_status,
            evidence=evidence,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TABLE_STRUCTURE_CONTRACT_VERSION:
            raise ValueError("unsupported table continuation version")
        confidence = self._validated_parts(
            self.structure_input_id,
            self.candidate_id,
            self.previous_region_id,
            self.current_region_id,
            self.previous_page_index,
            self.current_page_index,
            self.association_id,
            self.confidence,
            self.evidence_status,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        object.__setattr__(self, "confidence", confidence)
        if self.continuation_id != self._derived_id(
            self.structure_input_id,
            self.candidate_id,
            self.previous_region_id,
            self.current_region_id,
            self.previous_page_index,
            self.current_page_index,
            self.association_id,
            confidence,
            self.evidence_status,
            self.evidence,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        ):
            raise ValueError("table continuation ID is inconsistent")

    @classmethod
    def _validated_parts(
        cls,
        structure_input_id: str,
        candidate_id: str,
        previous_region_id: str,
        current_region_id: str,
        previous_page_index: int,
        current_page_index: int,
        association_id: str,
        confidence: float,
        evidence_status: TableStructureEvidenceStatus,
        evidence: Metadata,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> float:
        cls._validate_identity_fields(
            structure_input_id,
            candidate_id,
            previous_region_id,
            current_region_id,
            association_id,
            processor_name,
            processor_version,
            configuration_digest,
        )
        cls._validate_nonnegative_integer(
            "previous page index", previous_page_index
        )
        cls._validate_nonnegative_integer(
            "current page index", current_page_index
        )
        if current_page_index != previous_page_index + 1:
            raise ValueError("table continuation pages must be adjacent")
        if not isinstance(evidence_status, TableStructureEvidenceStatus):
            raise TypeError("continuation evidence status is unsupported")
        cls._validate_metadata(evidence)
        return cls._validate_unit_float("continuation confidence", confidence)

    @staticmethod
    def _derived_id(*values: object) -> str:
        return stable_id("table-continuation", *values)
