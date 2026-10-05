"""Nominal root for immutable ingestion identity records."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractIdentity(AbstractImmutableDataObject, ABC):
    """Nominal root for immutable ingestion identity records."""

    __slots__ = ()
