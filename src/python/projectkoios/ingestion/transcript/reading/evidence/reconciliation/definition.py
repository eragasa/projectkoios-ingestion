"""Exact expected-versus-observed reading inventory reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.expected import (  # noqa: E501
    ExpectedReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.reconciliation.field import (  # noqa: E501
    ReadingEvidenceInventoryField,
)
from projectkoios.ingestion.transcript.reading.evidence.reconciliation.mismatch import (  # noqa: E501
    ReadingEvidenceReconciliationMismatchInventory,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceReconciliation:
    """Compare independent expected and recomputed inventory values exactly."""

    expected: ExpectedReadingEvidenceInventory
    observed: ReadingEvidenceInventory
    mismatches: ReadingEvidenceReconciliationMismatchInventory = field(
        init=False
    )
    complete: bool = field(init=False)
    reconciliation_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.expected) is not ExpectedReadingEvidenceInventory:
            raise TypeError("expected has an unsupported type")
        if type(self.observed) is not ReadingEvidenceInventory:
            raise TypeError("observed has an unsupported type")
        fields = tuple(
            sorted(
                (
                    field_name
                    for field_name in ReadingEvidenceInventoryField
                    if getattr(self.expected.measures, field_name.value)
                    != getattr(self.observed.measures, field_name.value)
                ),
                key=lambda value: value.value,
            )
        )
        mismatches = ReadingEvidenceReconciliationMismatchInventory(*fields)
        object.__setattr__(self, "mismatches", mismatches)
        object.__setattr__(self, "complete", not mismatches)
        object.__setattr__(
            self,
            "reconciliation_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.RECONCILIATION,
                prefix="reading-evidence-reconciliation",
                material={
                    "expected_id": self.expected.expectation_id.value,
                    "observed_id": self.observed.inventory_id.value,
                    "mismatches": mismatches.identity_material(),
                },
            ),
        )
