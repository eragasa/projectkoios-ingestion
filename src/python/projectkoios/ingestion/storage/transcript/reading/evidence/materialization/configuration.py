"""Backend-neutral physical reading-evidence materialization mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.materializer.configuration import (
    AbstractMaterializationConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,119}")


@dataclass(frozen=True, slots=True)
class ReadingEvidenceMaterializationConfiguration(
    AbstractMaterializationConfiguration
):
    """Map logical roles to unique physical names and byte bounds."""

    CONTRACT_NAME: ClassVar[str] = (
        "reading-evidence-materialization-configuration"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    configuration_id: str
    schema_id: str
    schema_version: ReadingEvidenceStorageSchemaVersion
    documents_name: str
    pages_name: str
    blocks_name: str
    producers_name: str
    references_name: str
    limitations_name: str
    completions_name: str
    maximum_document_bytes: int
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        schema_version: ReadingEvidenceStorageSchemaVersion,
        documents_name: str,
        pages_name: str,
        blocks_name: str,
        producers_name: str,
        references_name: str,
        limitations_name: str,
        completions_name: str,
        maximum_document_bytes: int,
    ) -> ReadingEvidenceMaterializationConfiguration:
        """Create one complete physical mapping."""
        values = (
            schema_version.schema_id,
            documents_name,
            pages_name,
            blocks_name,
            producers_name,
            references_name,
            limitations_name,
            completions_name,
            maximum_document_bytes,
        )
        return cls(
            configuration_id=stable_id(
                "reading-evidence-materialization-configuration",
                cls.CONTRACT_VERSION,
                values,
            ),
            schema_id=schema_version.schema_id,
            schema_version=schema_version,
            documents_name=documents_name,
            pages_name=pages_name,
            blocks_name=blocks_name,
            producers_name=producers_name,
            references_name=references_name,
            limitations_name=limitations_name,
            completions_name=completions_name,
            maximum_document_bytes=maximum_document_bytes,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported materialization configuration")
        if type(self.schema_version) is not ReadingEvidenceStorageSchemaVersion:
            raise TypeError("schema_version has an unsupported type")
        if self.schema_id != self.schema_version.schema_id:
            raise ValueError("schema_id differs from schema_version")
        names = tuple(self.names().values())
        if any(
            type(value) is not str or not _NAME.fullmatch(value)
            for value in names
        ):
            raise ValueError("physical storage name is invalid")
        if len(names) != len(set(names)):
            raise ValueError("physical storage names must be unique")
        if (
            type(self.maximum_document_bytes) is not int
            or not 1
            <= self.maximum_document_bytes
            <= READING_EVIDENCE_LIMITS.maximum_single_record_bytes
        ):
            raise ValueError("materialization byte bound is invalid")
        expected = stable_id(
            "reading-evidence-materialization-configuration",
            self.CONTRACT_VERSION,
            (
                self.schema_version.schema_id,
                *names,
                self.maximum_document_bytes,
            ),
        )
        if self.configuration_id != expected:
            raise ValueError("materialization configuration ID is inconsistent")

    def names(self) -> dict[ReadingEvidenceStorageCollection, str]:
        """Return the exact logical-to-physical name mapping."""
        return {
            ReadingEvidenceStorageCollection.DOCUMENTS: self.documents_name,
            ReadingEvidenceStorageCollection.PAGES: self.pages_name,
            ReadingEvidenceStorageCollection.BLOCKS: self.blocks_name,
            ReadingEvidenceStorageCollection.PRODUCERS: self.producers_name,
            ReadingEvidenceStorageCollection.REFERENCES: self.references_name,
            ReadingEvidenceStorageCollection.LIMITATIONS: self.limitations_name,
            ReadingEvidenceStorageCollection.COMPLETIONS: self.completions_name,
        }
