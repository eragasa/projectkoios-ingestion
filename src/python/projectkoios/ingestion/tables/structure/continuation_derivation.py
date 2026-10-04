"""Immutable derivation of cross-page table continuations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

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
from projectkoios.ingestion.tables.structure.continuation import (
    TableContinuation,
)
from projectkoios.ingestion.tables.structure.evidence_status import (
    TableStructureEvidenceStatus,
)
from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)


@dataclass(frozen=True)
class TableContinuationDerivation(AbstractTableStructureDataObject):
    """Represent all continuation proposals for one table candidate."""

    CONTRACT_NAME: ClassVar[str] = "table-continuation-derivation"
    CONTRACT_VERSION: ClassVar[str] = TABLE_STRUCTURE_CONTRACT_VERSION

    continuations: tuple[TableContinuation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.continuations, tuple) or any(
            not isinstance(item, TableContinuation)
            for item in self.continuations
        ):
            raise TypeError(
                "continuation derivation requires immutable continuations"
            )

    @classmethod
    def create(
        cls,
        *,
        structure_input: TableStructureRequest,
        candidate: TableCandidate,
        processor_name: str,
        processor_version: str,
    ) -> TableContinuationDerivation:
        values: list[TableContinuation] = []
        for previous, current in zip(
            candidate.regions, candidate.regions[1:], strict=False
        ):
            association = next(
                (
                    item
                    for item in candidate.associations
                    if item.page_index == current.page_index
                    and item.role is TableAssociationRole.CONTINUATION_LABEL
                ),
                None,
            )
            if association is None:
                raise ValueError(
                    "multi-page table lacks continuation association"
                )
            values.append(
                TableContinuation.create(
                    structure_input_id=structure_input.input_id,
                    candidate_id=candidate.candidate_id,
                    previous_region_id=previous.region_evidence_id,
                    current_region_id=current.region_evidence_id,
                    previous_page_index=previous.page_index,
                    current_page_index=current.page_index,
                    association_id=association.association_id,
                    confidence=min(previous.confidence, current.confidence),
                    evidence_status=TableStructureEvidenceStatus.PROPOSED,
                    evidence=(("method", "explicit_continuation_label"),),
                    processor_name=processor_name,
                    processor_version=processor_version,
                    configuration_digest=(
                        structure_input.configuration.configuration_digest
                    ),
                )
            )
        if len(values) > structure_input.configuration.max_continuations:
            raise TableStructureLimitError(
                "continuations exceed max_continuations"
            )
        return cls(continuations=tuple(values))
