"""Nominal root for ingestion-owned data objects."""

from __future__ import annotations

from abc import ABC

from projectkoios.base import DataObject


class AbstractDataObject(DataObject, ABC):
    """Nominal root for ingestion-owned data objects."""

    __slots__ = ()
