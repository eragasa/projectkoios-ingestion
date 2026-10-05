"""Authoritative immutable evidence accepted by ingestion projectors."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractProjectionSource(AbstractImmutableDataObject, ABC):
    """Require stable evidence identity and canonical content identity."""

    __slots__ = ()

    evidence_id: str
    canonical_sha256: str
