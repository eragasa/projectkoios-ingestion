"""Authoritative immutable evidence accepted by ingestion projectors."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractProjectionSource(AbstractImmutableDataObject, ABC):
    """Define immutable source evidence accepted by a projector.

    Attributes
    ----------
    evidence_id
        Stable domain identity of the complete evidence value.
    canonical_sha256
        Lowercase SHA-256 digest of its canonical content.

    Notes
    -----
    A source value must be complete before projection begins. Implementations
    cannot defer required facts to mutable lookups performed by the projector.
    """

    __slots__ = ()

    evidence_id: str
    canonical_sha256: str
