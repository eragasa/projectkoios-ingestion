"""Rebuildable immutable values produced by ingestion projectors."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractProjectionValue(AbstractImmutableDataObject, ABC):
    """Define an immutable rebuildable value produced by a projector.

    Attributes
    ----------
    projection_id
        Stable identity of the complete projection value.
    source_evidence_ids
        Canonically ordered identities of all contributing source evidence.
    schema_id
        Logical schema required by compatible consumers or materializers.
    canonical_sha256
        Lowercase SHA-256 digest of canonical projection content.
    """

    __slots__ = ()

    projection_id: str
    source_evidence_ids: tuple[str, ...]
    schema_id: str
    canonical_sha256: str
