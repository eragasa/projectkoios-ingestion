"""Independent expected canonical reading evidence inventories."""

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
from projectkoios.ingestion.transcript.reading.evidence.inventory.measures import (  # noqa: E501
    ReadingEvidenceInventoryMeasures,
)


@dataclass(frozen=True, slots=True)
class ExpectedReadingEvidenceInventory:
    """Bind an independently frozen complete current-contract expectation."""

    measures: ReadingEvidenceInventoryMeasures
    expectation_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.measures) is not ReadingEvidenceInventoryMeasures:
            raise TypeError("measures must be ReadingEvidenceInventoryMeasures")
        object.__setattr__(
            self,
            "expectation_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.EVIDENCE_INVENTORY,
                prefix="expected-reading-evidence-inventory",
                material={"measures_id": self.measures.measures_id.value},
            ),
        )
