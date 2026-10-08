"""Identity-bound canonical reading limitations."""

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
from projectkoios.ingestion.transcript.reading.evidence.limitation.affected import (  # noqa: E501
    ReadingAffectedEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.code import (
    ReadingEvidenceLimitationCode,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceLimitation:
    """Record one exact limitation without accepting or repairing evidence."""

    code: ReadingEvidenceLimitationCode
    affected_ids: ReadingAffectedEvidenceIdentityInventory
    limitation_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.code, ReadingEvidenceLimitationCode):
            raise TypeError("code must be ReadingEvidenceLimitationCode")
        if (
            type(self.affected_ids)
            is not ReadingAffectedEvidenceIdentityInventory
        ):
            raise TypeError("affected_ids has an unsupported type")
        object.__setattr__(
            self,
            "limitation_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.LIMITATION,
                prefix="reading-evidence-limitation",
                material={
                    "code": self.code,
                    "affected_ids": self.affected_ids.identity_material(),
                },
            ),
        )
