"""Observed evidence for one extraction projection index."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.projection.index.readiness.definition import (  # noqa: E501
    ExtractionProjectionIndexDefinition,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionIndexEvidence(AbstractImmutableDataObject):
    """Bind an expected index definition to exact observed properties."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-index-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_KEYS: ClassVar[int] = 16
    MAXIMUM_NAME_LENGTH: ClassVar[int] = 255

    index_evidence_id: str
    index_definition_id: str
    collection_name: str
    index_name: str
    keys: tuple[tuple[str, int], ...]
    unique: bool
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        definition: ExtractionProjectionIndexDefinition,
        index_name: str,
        keys: tuple[tuple[str, int], ...],
        unique: bool,
    ) -> ExtractionProjectionIndexEvidence:
        """Create observed evidence bound to its expected definition."""
        if (
            index_name != definition.index_name
            or keys != definition.keys
            or unique is not definition.unique
        ):
            raise ValueError("observed index differs from its definition")
        return cls(
            index_evidence_id=stable_id(
                "extraction-projection-index-evidence",
                cls.CONTRACT_VERSION,
                definition.index_definition_id,
                definition.collection_name,
                index_name,
                keys,
                unique,
            ),
            index_definition_id=definition.index_definition_id,
            collection_name=definition.collection_name,
            index_name=index_name,
            keys=keys,
            unique=unique,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction index evidence")
        if any(
            type(value) is not str
            or not value
            or len(value) > self.MAXIMUM_NAME_LENGTH
            for value in (
                self.index_definition_id,
                self.collection_name,
                self.index_name,
            )
        ):
            raise ValueError("extraction index evidence is incomplete")
        if (
            not isinstance(self.keys, tuple)
            or not self.keys
            or len(self.keys) > self.MAXIMUM_KEYS
            or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or type(item[0]) is not str
                or not item[0]
                or len(item[0]) > self.MAXIMUM_NAME_LENGTH
                or item[1] not in (-1, 1)
                for item in self.keys
            )
        ):
            raise ValueError("observed extraction index keys are invalid")
        if type(self.unique) is not bool:
            raise TypeError("observed index uniqueness must be boolean")
        expected = stable_id(
            "extraction-projection-index-evidence",
            self.CONTRACT_VERSION,
            self.index_definition_id,
            self.collection_name,
            self.index_name,
            self.keys,
            self.unique,
        )
        if self.index_evidence_id != expected:
            raise ValueError("extraction index evidence ID is inconsistent")
