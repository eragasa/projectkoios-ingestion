"""Nominal request accepted by configurable ingestion actionizers."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)


class ConfigurableDataObjectActionRequest[
    ConfigurationT: AbstractActionConfiguration,
](DataObjectActionRequest, ABC):
    """Require one complete immutable configuration on an action request.

    Attributes
    ----------
    configuration
        Complete immutable configuration for the requested action.
    """

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str]
    configuration: ConfigurationT
