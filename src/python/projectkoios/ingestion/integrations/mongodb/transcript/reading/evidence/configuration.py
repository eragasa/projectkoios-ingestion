"""MongoDB front-end configuration for canonical reading evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.configuration import (  # noqa: E501
    ReadingEvidenceMaterializationConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)

_INDEX_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}")


@dataclass(frozen=True, slots=True)
class MongoReadingEvidenceConfiguration:
    """Compose neutral physical mapping with MongoDB query bounds."""

    materialization: ReadingEvidenceMaterializationConfiguration
    cursor_batch_size: int
    scope_index_name: str
    configuration_id: str = field(init=False)

    @classmethod
    def v1(cls) -> MongoReadingEvidenceConfiguration:
        """Return explicit current MongoDB physical names and bounds."""
        return cls(
            materialization=(
                ReadingEvidenceMaterializationConfiguration.create(
                    schema_version=ReadingEvidenceStorageSchemaVersion.current(),
                    documents_name="reading_evidence_documents_v1",
                    pages_name="reading_evidence_pages_v1",
                    blocks_name="reading_evidence_blocks_v1",
                    producers_name="reading_evidence_producers_v1",
                    references_name="reading_evidence_references_v1",
                    limitations_name="reading_evidence_limitations_v1",
                    completions_name="reading_evidence_completions_v1",
                    maximum_document_bytes=4_194_304,
                )
            ),
            cursor_batch_size=1_000,
            scope_index_name="reading_evidence_scope_v1",
        )

    def scope_index_keys(self) -> tuple[tuple[str, int], ...]:
        """Return the exact current MongoDB scope-index key sequence."""
        return (
            ("schema_id", 1),
            ("generation_id", 1),
            ("evidence_document_id", 1),
            ("_id", 1),
        )

    def matches_scope_index(self, value: Mapping[str, object]) -> bool:
        """Return whether a provider index is the exact supported definition."""
        if not isinstance(value, Mapping):
            return False
        keys = value.get("key")
        if not isinstance(keys, (list, tuple)):
            return False
        if tuple(keys) != self.scope_index_keys():
            return False
        return not (
            set(value)
            - {
                "key",
                "name",
                "ns",
                "v",
            }
        )

    def __post_init__(self) -> None:
        if (
            type(self.materialization)
            is not ReadingEvidenceMaterializationConfiguration
        ):
            raise TypeError("materialization has an unsupported type")
        if (
            type(self.cursor_batch_size) is not int
            or not 1 <= self.cursor_batch_size <= 10_000
        ):
            raise ValueError("cursor_batch_size is invalid")
        if type(self.scope_index_name) is not str or not _INDEX_NAME.fullmatch(
            self.scope_index_name
        ):
            raise ValueError("scope_index_name is invalid")
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                "mongodb-reading-evidence-configuration",
                self.materialization.configuration_id,
                self.cursor_batch_size,
                self.scope_index_name,
            ),
        )
