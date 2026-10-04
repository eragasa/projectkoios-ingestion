"""Immutable validation evidence for table continuations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.tables.contracts import (
    TableAssociationRole,
    TableCandidate,
)
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.constants import (
    TABLE_STRUCTURE_CONTRACT_VERSION,
)
from projectkoios.ingestion.tables.structure.structure import TableStructure


@dataclass(frozen=True)
class TableContinuationValidation(
    AbstractTableStructureDataObject, AbstractValidation
):
    """Record successful validation of cross-page continuation evidence."""

    CONTRACT_NAME: ClassVar[str] = "table-continuation-validation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    structure_id: str
    validated_continuation_count: int

    def __post_init__(self) -> None:
        self._validate_identity_fields(self.structure_id)
        self._validate_nonnegative_integer(
            "validated continuation count",
            self.validated_continuation_count,
        )

    @classmethod
    def create(
        cls,
        *,
        structure: TableStructure,
        candidate: TableCandidate,
    ) -> TableContinuationValidation:
        association_by_id = {
            association.association_id: association
            for association in candidate.associations
        }
        for continuation in structure.continuations:
            association = association_by_id.get(continuation.association_id)
            if (
                association is None
                or association.role
                is not TableAssociationRole.CONTINUATION_LABEL
                or association.page_index != continuation.current_page_index
            ):
                raise ValueError("continuation association is inconsistent")
            if (
                continuation.structure_input_id != structure.structure_input_id
                or continuation.candidate_id != structure.candidate_id
                or continuation.processor_name != structure.processor_name
                or continuation.processor_version != structure.processor_version
                or continuation.configuration_digest
                != structure.configuration_digest
            ):
                raise ValueError(
                    "continuation derivation evidence is inconsistent"
                )
        continuation_pairs = tuple(
            (item.previous_region_id, item.current_region_id)
            for item in structure.continuations
        )
        expected_pairs = tuple(
            (left.region_evidence_id, right.region_evidence_id)
            for left, right in zip(
                candidate.regions, candidate.regions[1:], strict=False
            )
        )
        if continuation_pairs != expected_pairs:
            raise ValueError("table continuations are inconsistent")
        return cls(
            structure_id=structure.structure_id,
            validated_continuation_count=len(structure.continuations),
        )
