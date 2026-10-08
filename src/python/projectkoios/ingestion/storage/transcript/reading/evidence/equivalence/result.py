"""Immutable reading-evidence equivalence results."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.mismatch import (  # noqa: E501
    ReadingEvidenceEquivalenceMismatchInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.equivalence.request import (  # noqa: E501
    ReadingEvidenceEquivalenceRequest,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceEquivalenceResult(DataObjectActionResult):
    """Report technical equivalence without implying operator approval."""

    request: ReadingEvidenceEquivalenceRequest
    mismatches: ReadingEvidenceEquivalenceMismatchInventory
    verifier_id: str
    equivalent: bool = field(init=False)
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not ReadingEvidenceEquivalenceRequest:
            raise TypeError("request has an unsupported type")
        if (
            type(self.mismatches)
            is not ReadingEvidenceEquivalenceMismatchInventory
        ):
            raise TypeError("mismatches have an unsupported type")
        if type(self.verifier_id) is not str or not self.verifier_id:
            raise ValueError("verifier_id must be non-empty")
        if len(self.verifier_id.encode("utf-8", errors="strict")) > 512:
            raise ValueError("verifier_id exceeds its limit")
        equivalent = len(self.mismatches) == 0
        object.__setattr__(self, "equivalent", equivalent)
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "reading-evidence-equivalence-result",
                self.request.request_id,
                tuple(value.value for value in self.mismatches),
                self.verifier_id,
                equivalent,
            ),
        )
