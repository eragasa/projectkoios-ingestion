"""Complete deterministic configuration accepted by ingestion projectors."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractProjectionConfiguration(AbstractImmutableDataObject, ABC):
    """Require one stable identity for complete projection configuration."""

    __slots__ = ()

    configuration_id: str
