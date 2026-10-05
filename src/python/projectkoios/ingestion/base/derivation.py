"""Nominal root for immutable ingestion derivation records."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractDerivation(AbstractImmutableDataObject, ABC):
    """Nominal root for immutable evidence-derived records."""

    __slots__ = ()
