"""Explicit immutable targets observed by inventories."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from projectkoios.ingestion.base.identity import AbstractIdentity


class AbstractInventoryTarget(AbstractIdentity, ABC):
    """Require a stable identity for one externally observed resource."""

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str]
    target_id: str
