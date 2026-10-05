"""Aggregate extraction projection index-readiness evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import canonical_json, stable_id
from projectkoios.ingestion.storage.extraction.projection.index_readiness.index_evidence import (  # noqa: E501
    ExtractionProjectionIndexEvidence,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionIndexReadinessEvidence(AbstractImmutableDataObject):
    """Bind exact observed indexes to target, configuration, and authority."""

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-index-readiness-evidence"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_INDEXES: ClassVar[int] = 64

    readiness_id: str
    target_id: str
    configuration_id: str
    authority_id: str
    schema_id: str
    canonical_sha256: str
    indexes: tuple[ExtractionProjectionIndexEvidence, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        target_id: str,
        configuration_id: str,
        authority_id: str,
        schema_id: str,
        indexes: tuple[ExtractionProjectionIndexEvidence, ...],
    ) -> ExtractionProjectionIndexReadinessEvidence:
        """Create one complete readiness observation."""
        values = (
            target_id,
            configuration_id,
            authority_id,
            schema_id,
            tuple(item.index_evidence_id for item in indexes),
        )
        digest = hashlib.sha256(
            canonical_json(values).encode("utf-8")
        ).hexdigest()
        return cls(
            readiness_id=stable_id(
                "extraction-projection-index-readiness-evidence",
                cls.CONTRACT_VERSION,
                values,
                digest,
            ),
            target_id=target_id,
            configuration_id=configuration_id,
            authority_id=authority_id,
            schema_id=schema_id,
            canonical_sha256=digest,
            indexes=indexes,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported index-readiness evidence")
        texts = (
            self.target_id,
            self.configuration_id,
            self.authority_id,
            self.schema_id,
        )
        if any(
            type(value) is not str or not value or len(value) > 4_096
            for value in texts
        ):
            raise ValueError("index-readiness provenance is incomplete")
        if (
            not isinstance(self.indexes, tuple)
            or len(self.indexes) > self.MAXIMUM_INDEXES
            or any(
                type(item) is not ExtractionProjectionIndexEvidence
                for item in self.indexes
            )
        ):
            raise TypeError("index-readiness evidence entries are invalid")
        keys = tuple(
            (item.collection_name, item.index_name) for item in self.indexes
        )
        if not keys or keys != tuple(sorted(set(keys))):
            raise ValueError("index-readiness evidence is not canonical")
        values = (
            *texts,
            tuple(item.index_evidence_id for item in self.indexes),
        )
        digest = hashlib.sha256(
            canonical_json(values).encode("utf-8")
        ).hexdigest()
        if self.canonical_sha256 != digest:
            raise ValueError("index-readiness evidence digest is inconsistent")
        expected = stable_id(
            "extraction-projection-index-readiness-evidence",
            self.CONTRACT_VERSION,
            values,
            digest,
        )
        if self.readiness_id != expected:
            raise ValueError("index-readiness evidence ID is inconsistent")
