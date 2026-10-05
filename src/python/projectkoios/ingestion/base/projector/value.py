"""Rebuildable immutable values produced by ingestion projectors."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractProjectionValue(AbstractImmutableDataObject, ABC):
    """Require provenance, schema, and canonical content identities."""

    __slots__ = ()

    projection_id: str
    source_evidence_ids: tuple[str, ...]
    schema_id: str
    canonical_sha256: str
