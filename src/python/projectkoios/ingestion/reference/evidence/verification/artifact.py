"""Semantic exact-artifact verification coverage."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum


class ReferenceEvidenceVerifiedArtifact(StrEnum):
    """Optional producer artifact classes verified by exact bytes."""

    EXTRACTION = "extraction"
    CLEAN_TRANSCRIPT = "clean_transcript"
    DERIVATION_AUDIT = "derivation_audit"


_VERIFIED_ARTIFACT_ORDER = {
    ReferenceEvidenceVerifiedArtifact.EXTRACTION: 0,
    ReferenceEvidenceVerifiedArtifact.CLEAN_TRANSCRIPT: 1,
    ReferenceEvidenceVerifiedArtifact.DERIVATION_AUDIT: 2,
}


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceVerifiedArtifactInventory:
    """Own unique verified-artifact kinds in schema order."""

    _artifacts: tuple[ReferenceEvidenceVerifiedArtifact, ...] = field(
        repr=False
    )

    def __init__(self, *artifacts: ReferenceEvidenceVerifiedArtifact) -> None:
        values = tuple(artifacts)
        if any(
            not isinstance(item, ReferenceEvidenceVerifiedArtifact)
            for item in values
        ):
            raise TypeError(
                "verified_artifacts must contain verified artifact kinds"
            )
        if len(set(values)) != len(values):
            raise ValueError("verified artifact kinds must be unique")
        if (
            tuple(sorted(values, key=_VERIFIED_ARTIFACT_ORDER.__getitem__))
            != values
        ):
            raise ValueError("verified artifact kinds must be in schema order")
        object.__setattr__(self, "_artifacts", values)

    def __iter__(self) -> Iterator[ReferenceEvidenceVerifiedArtifact]:
        return iter(self._artifacts)

    def __len__(self) -> int:
        return len(self._artifacts)
