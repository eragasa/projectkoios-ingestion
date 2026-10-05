"""Complete immutable configuration accepted by inventories."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)


class AbstractInventoryConfiguration(AbstractActionConfiguration, ABC):
    """Require a stable identity for every inventory observation choice."""

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str]
