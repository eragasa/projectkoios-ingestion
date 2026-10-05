"""Nominal base for equation representations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractEquation(AbstractImmutableDataObject, ABC):
    """Nominal root for one immutable equation representation."""

    __slots__ = ()

    MAX_SOURCE_IDS: ClassVar[int] = 256
    MAX_SOURCE_ID_CHARACTERS: ClassVar[int] = 4_096

    @property
    @abstractmethod
    def equation_id(self) -> str:
        """Return the stable identity of this exact representation."""

    @property
    @abstractmethod
    def equation_source_ids(self) -> tuple[str, ...]:
        """Return exact upstream identities in retained order."""

    @classmethod
    def _validate_source_ids(cls, values: tuple[str, ...]) -> None:
        if type(values) is not tuple:
            raise TypeError("equation source IDs must be a tuple")
        if (
            not values
            or len(values) > cls.MAX_SOURCE_IDS
            or len(values) != len(set(values))
        ):
            raise ValueError(
                "equation source IDs must be nonempty, bounded, and unique"
            )
        if any(
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > cls.MAX_SOURCE_ID_CHARACTERS
            for value in values
        ):
            raise ValueError("equation source IDs are invalid")
