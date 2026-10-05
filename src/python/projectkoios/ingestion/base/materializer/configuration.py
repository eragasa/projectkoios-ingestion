"""Complete immutable configuration accepted by materializers."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)


class AbstractMaterializationConfiguration(AbstractActionConfiguration, ABC):
    """Define every deterministic target-write choice.

    Attributes
    ----------
    configuration_id
        Stable identity binding all physical mapping and write-policy choices.
    schema_id
        Logical projection schema consumed by the configuration.

    Notes
    -----
    Connection credentials and mutable clients are capabilities owned by a
    concrete adapter. Collection names, byte bounds, and other choices that can
    change writes belong in configuration.
    """

    __slots__ = ()

    configuration_id: str
    schema_id: str
