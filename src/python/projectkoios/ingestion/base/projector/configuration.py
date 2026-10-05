"""Complete deterministic configuration accepted by ingestion projectors."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)


class AbstractProjectionConfiguration(AbstractActionConfiguration, ABC):
    """Define complete immutable deterministic projector configuration.

    Attributes
    ----------
    configuration_id
        Stable identity binding every configuration choice.

    Notes
    -----
    Hidden defaults and environment lookups are incompatible with this
    contract. A concrete configuration must carry every choice that can change
    projection output.
    """

    __slots__ = ()

    configuration_id: str
