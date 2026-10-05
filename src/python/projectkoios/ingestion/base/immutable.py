"""Nominal root for immutable ingestion data objects."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from projectkoios.ingestion.base.data_object import AbstractDataObject


class AbstractImmutableDataObject(AbstractDataObject, ABC):
    """Nominal root for versioned immutable ingestion data objects."""

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str]
    CONTRACT_VERSION: ClassVar[str]
