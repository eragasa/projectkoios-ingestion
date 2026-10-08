"""Immutable MongoDB reading-evidence index-readiness results."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.index.readiness.request import (  # noqa: E501
    MongoReadingEvidenceIndexReadinessRequest,
)


@dataclass(frozen=True, slots=True)
class MongoReadingEvidenceIndexReadinessResult(DataObjectActionResult):
    """Report exact created and unchanged scope-index counts."""

    request: MongoReadingEvidenceIndexReadinessRequest
    created_count: int
    unchanged_count: int
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not MongoReadingEvidenceIndexReadinessRequest:
            raise TypeError("request has an unsupported type")
        for value, name in (
            (self.created_count, "created_count"),
            (self.unchanged_count, "unchanged_count"),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be non-negative")
        expected = len(self.request.configuration.materialization.names())
        if self.created_count + self.unchanged_count != expected:
            raise ValueError("index-readiness collection coverage differs")
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "mongodb-reading-evidence-index-readiness-result",
                self.request.request_id,
                self.created_count,
                self.unchanged_count,
            ),
        )
