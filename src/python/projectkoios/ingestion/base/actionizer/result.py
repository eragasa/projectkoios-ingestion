"""Nominal immutable result produced by ingestion actionizers."""

from __future__ import annotations

from abc import ABC

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractDataObjectActionResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
    ABC,
):
    """Identify one immutable result of an ingestion-owned action."""

    __slots__ = ()
