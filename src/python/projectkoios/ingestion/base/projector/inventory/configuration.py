"""Projection-bound inventory configuration."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.inventory.configuration import (
    AbstractInventoryConfiguration,
)


class AbstractProjectorInventoryConfiguration(
    AbstractInventoryConfiguration,
    ABC,
):
    """Require the logical projection schema being inventoried."""

    __slots__ = ()

    schema_id: str
