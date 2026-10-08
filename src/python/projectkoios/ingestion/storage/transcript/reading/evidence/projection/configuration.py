"""Complete backend-neutral reading-evidence storage projection choices."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.configuration import (
    AbstractProjectionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)

_GENERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,255}")


@dataclass(frozen=True, slots=True)
class ReadingEvidenceStorageProjectionConfiguration(
    AbstractProjectionConfiguration
):
    """Bind every deterministic logical persistence choice."""

    CONTRACT_NAME: ClassVar[str] = (
        "reading-evidence-storage-projection-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    schema_version: ReadingEvidenceStorageSchemaVersion
    generation_id: str
    completion_state: str
    maximum_record_count: int
    maximum_document_bytes: int
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def v1(
        cls, *, generation_id: str
    ) -> ReadingEvidenceStorageProjectionConfiguration:
        """Return complete current-schema choices for one generation."""
        schema = ReadingEvidenceStorageSchemaVersion.current()
        values = (
            schema.schema_id,
            generation_id,
            "complete",
            READING_EVIDENCE_LIMITS.maximum_records,
            READING_EVIDENCE_LIMITS.maximum_single_record_bytes,
        )
        return cls(
            configuration_id=stable_id(
                "reading-evidence-storage-configuration",
                cls.CONTRACT_VERSION,
                values,
            ),
            schema_version=schema,
            generation_id=generation_id,
            completion_state=values[2],
            maximum_record_count=values[3],
            maximum_document_bytes=values[4],
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported storage projection configuration")
        if type(self.schema_version) is not ReadingEvidenceStorageSchemaVersion:
            raise TypeError("schema_version has an unsupported type")
        if not _GENERATION.fullmatch(self.generation_id):
            raise ValueError("generation_id is invalid")
        if self.completion_state != "complete":
            raise ValueError("completion_state must be complete")
        if (
            type(self.maximum_record_count) is not int
            or not 1
            <= self.maximum_record_count
            <= READING_EVIDENCE_LIMITS.maximum_records
        ):
            raise ValueError("maximum_record_count is invalid")
        if (
            type(self.maximum_document_bytes) is not int
            or not 1
            <= self.maximum_document_bytes
            <= READING_EVIDENCE_LIMITS.maximum_single_record_bytes
        ):
            raise ValueError("maximum_document_bytes is invalid")
        values = (
            self.schema_version.schema_id,
            self.generation_id,
            self.completion_state,
            self.maximum_record_count,
            self.maximum_document_bytes,
        )
        expected = stable_id(
            "reading-evidence-storage-configuration",
            self.CONTRACT_VERSION,
            values,
        )
        if self.configuration_id != expected:
            raise ValueError("storage configuration identity is inconsistent")
