"""Projection-bound inventory evidence."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.inventory.evidence import (
    AbstractInventoryEvidence,
)


class AbstractProjectorInventoryEvidence(
    AbstractInventoryEvidence,
    ABC,
):
    """Require the logical projection schema proven by observed evidence."""

    __slots__ = ()

    schema_id: str
