"""Projection-bound targets observed by projector inventories."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.inventory.target import AbstractInventoryTarget


class AbstractProjectorInventoryTarget(AbstractInventoryTarget, ABC):
    """Require the logical projection schema exposed by a target."""

    __slots__ = ()

    schema_id: str
