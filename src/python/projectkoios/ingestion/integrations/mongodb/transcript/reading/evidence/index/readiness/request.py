"""Immutable MongoDB reading-evidence index-readiness requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.mongodb.transcript.reading.evidence.configuration import (  # noqa: E501
    MongoReadingEvidenceConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)


@dataclass(frozen=True, slots=True)
class MongoReadingEvidenceIndexReadinessRequest(DataObjectActionRequest):
    """Bind one exact target, physical mapping, and write authority."""

    target: ReadingEvidenceMaterializationTarget
    configuration: MongoReadingEvidenceConfiguration
    authority_id: str
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.target) is not ReadingEvidenceMaterializationTarget:
            raise TypeError("target has an unsupported type")
        if type(self.configuration) is not MongoReadingEvidenceConfiguration:
            raise TypeError("configuration has an unsupported type")
        if (
            self.target.schema_id
            != self.configuration.materialization.schema_id
        ):
            raise ValueError("target and configuration schemas differ")
        if type(self.authority_id) is not str or not self.authority_id:
            raise ValueError("authority_id must be non-empty")
        if len(self.authority_id.encode("utf-8", errors="strict")) > 512:
            raise ValueError("authority_id exceeds its limit")
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "mongodb-reading-evidence-index-readiness-request",
                self.target.target_id,
                self.configuration.configuration_id,
                self.authority_id,
            ),
        )
