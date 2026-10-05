"""Nominal configuration shared by configurable ingestion actions."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractActionConfiguration(AbstractImmutableDataObject, ABC):
    """Require one stable identity for complete action configuration.

    Attributes
    ----------
    configuration_id
        Stable identity binding every deterministic action choice.
    """

    __slots__ = ()

    configuration_id: str
