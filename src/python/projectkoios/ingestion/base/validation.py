"""Nominal root for immutable ingestion validation records."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractValidation(AbstractImmutableDataObject, ABC):
    """Nominal root for immutable contract-validation records."""

    __slots__ = ()
