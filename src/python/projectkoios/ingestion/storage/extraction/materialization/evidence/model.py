"""Immutable evidence from extraction projection materialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.materializer.evidence import (
    AbstractMaterializationEvidence,
)
from projectkoios.ingestion.identity import canonical_json, stable_id
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.storage.extraction.materialization.evidence.collection import (  # noqa: E501
    ExtractionProjectionMaterializationCollectionEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)


@dataclass(frozen=True, slots=True)
class ExtractionProjectionMaterializationEvidence(
    AbstractMaterializationEvidence
):
    """Report exact create-once outcomes for one extraction read model.

    Parameters
    ----------
    evidence_id
        Stable identity over provenance, counts, and collection evidence.
    projection_id
        Exact extraction read model applied to the target.
    target_id
        Exact external target resource identity.
    configuration_id
        Exact physical collection and byte-bound configuration.
    authority_id
        Exact authority identity presented for the writes.
    canonical_sha256
        Digest over canonical compact outcome evidence.
    projected_document_count
        Total documents in the input read model.
    created_document_count
        Documents newly created by this invocation.
    unchanged_document_count
        Exact prior documents verified and replaced idempotently.
    collections
        Canonically ordered per-logical-collection count evidence.
    contract_version
        Version of this materialization evidence contract.
    """

    CONTRACT_NAME: ClassVar[str] = (
        "extraction-projection-materialization-evidence"
    )
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    evidence_id: str
    projection_id: str
    target_id: str
    configuration_id: str
    authority_id: str
    canonical_sha256: str
    projected_document_count: int
    created_document_count: int
    unchanged_document_count: int
    collections: tuple[
        ExtractionProjectionMaterializationCollectionEvidence,
        ...,
    ]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection_id: str,
        target_id: str,
        configuration_id: str,
        authority_id: str,
        projected_document_count: int,
        collections: tuple[
            ExtractionProjectionMaterializationCollectionEvidence,
            ...,
        ],
    ) -> ExtractionProjectionMaterializationEvidence:
        """Create aggregate evidence from exact collection outcomes."""
        created = sum(item.created_document_count for item in collections)
        unchanged = sum(item.unchanged_document_count for item in collections)
        values = (
            projection_id,
            target_id,
            configuration_id,
            authority_id,
            projected_document_count,
            created,
            unchanged,
            tuple(item.collection_evidence_id for item in collections),
        )
        digest = SHA256Fingerprinter.fingerprint(
            content=canonical_json(values).encode("utf-8")
        )
        return cls(
            evidence_id=stable_id(
                "extraction-projection-materialization-evidence",
                cls.CONTRACT_VERSION,
                values,
                digest,
            ),
            projection_id=projection_id,
            target_id=target_id,
            configuration_id=configuration_id,
            authority_id=authority_id,
            canonical_sha256=digest,
            projected_document_count=projected_document_count,
            created_document_count=created,
            unchanged_document_count=unchanged,
            collections=collections,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported materialization evidence contract")
        for name, text_value in (
            ("projection_id", self.projection_id),
            ("target_id", self.target_id),
            ("configuration_id", self.configuration_id),
            ("authority_id", self.authority_id),
        ):
            if type(text_value) is not str or not text_value:
                raise ValueError(f"materialization evidence {name} is invalid")
        if not isinstance(self.collections, tuple) or any(
            type(item)
            is not ExtractionProjectionMaterializationCollectionEvidence
            for item in self.collections
        ):
            raise TypeError("materialization collection evidence is invalid")
        expected_collections = tuple(ExtractionProjectionCollection)
        actual_collections = tuple(item.collection for item in self.collections)
        if actual_collections != expected_collections:
            raise ValueError("materialization collections are not canonical")
        created = sum(item.created_document_count for item in self.collections)
        unchanged = sum(
            item.unchanged_document_count for item in self.collections
        )
        for count in (
            self.projected_document_count,
            self.created_document_count,
            self.unchanged_document_count,
        ):
            if (
                isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise ValueError("materialization aggregate count is invalid")
        if (
            self.created_document_count != created
            or self.unchanged_document_count != unchanged
            or self.projected_document_count != created + unchanged
        ):
            raise ValueError("materialization aggregate counts differ")
        values = (
            self.projection_id,
            self.target_id,
            self.configuration_id,
            self.authority_id,
            self.projected_document_count,
            self.created_document_count,
            self.unchanged_document_count,
            tuple(item.collection_evidence_id for item in self.collections),
        )
        digest = SHA256Fingerprinter.fingerprint(
            content=canonical_json(values).encode("utf-8")
        )
        if self.canonical_sha256 != digest:
            raise ValueError("materialization evidence digest is inconsistent")
        expected = stable_id(
            "extraction-projection-materialization-evidence",
            self.CONTRACT_VERSION,
            values,
            digest,
        )
        if self.evidence_id != expected:
            raise ValueError("materialization evidence ID is inconsistent")
