"""Expected MongoDB index definition for extraction projection readiness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ExtractionProjectionIndexDefinition(AbstractImmutableDataObject):
    """Bind one physical collection to one ordered index definition."""

    CONTRACT_NAME: ClassVar[str] = "extraction-projection-index-definition"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_KEYS: ClassVar[int] = 16
    MAXIMUM_NAME_LENGTH: ClassVar[int] = 255

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
        collection_name: str,
        index_name: str,
        keys: tuple[tuple[str, int], ...],
        unique: bool,
    ) -> ExtractionProjectionIndexDefinition:
        """Create one exact ordered index definition."""
        return cls(
            index_definition_id=stable_id(
                "extraction-projection-index-definition",
                cls.CONTRACT_VERSION,
                collection_name,
                index_name,
                keys,
                unique,
            ),
            collection_name=collection_name,
            index_name=index_name,
            keys=keys,
            unique=unique,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction index definition")
        if any(
            type(value) is not str
            or not value
            or len(value) > self.MAXIMUM_NAME_LENGTH
            for value in (self.collection_name, self.index_name)
        ):
            raise ValueError("extraction index identity is incomplete")
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
            or len({name for name, _ in self.keys}) != len(self.keys)
        ):
            raise ValueError("extraction index keys are invalid")
        if type(self.unique) is not bool:
            raise TypeError("extraction index uniqueness must be boolean")
        expected = stable_id(
            "extraction-projection-index-definition",
            self.CONTRACT_VERSION,
            self.collection_name,
            self.index_name,
            self.keys,
            self.unique,
        )
        if self.index_definition_id != expected:
            raise ValueError("extraction index definition ID is inconsistent")
