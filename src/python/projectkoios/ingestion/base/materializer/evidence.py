"""Immutable evidence produced by ingestion materializers."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractMaterializationEvidence(AbstractImmutableDataObject, ABC):
    """Bind observed write outcomes to exact input and target identities.

    Attributes
    ----------
    evidence_id
        Stable identity of the complete materialization evidence.
    projection_id
        Exact immutable projection value that was applied.
    target_id
        Exact external target that received the projection.
    configuration_id
        Exact physical mapping and write configuration.
    authority_id
        Exact authority identity presented for the completed effects.
    canonical_sha256
        Lowercase SHA-256 digest of canonical outcome evidence.
    """

    __slots__ = ()

    evidence_id: str
    projection_id: str
    target_id: str
    configuration_id: str
    authority_id: str
    canonical_sha256: str
