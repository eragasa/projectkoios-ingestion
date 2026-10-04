from __future__ import annotations

from abc import ABC
from typing import ClassVar

from projectkoios.base import DataObject


class AbstractDataObject(DataObject, ABC):
    """Nominal root for ingestion-owned data objects."""

    __slots__ = ()


class AbstractImmutableDataObject(AbstractDataObject, ABC):
    """Nominal root for versioned immutable ingestion data objects."""

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str]
    CONTRACT_VERSION: ClassVar[str]


class AbstractIdentity(AbstractImmutableDataObject, ABC):
    """Nominal root for immutable ingestion identity records."""

    __slots__ = ()


class AbstractDerivation(AbstractImmutableDataObject, ABC):
    """Nominal root for immutable evidence-derived records."""

    __slots__ = ()


class AbstractValidation(AbstractImmutableDataObject, ABC):
    """Nominal root for immutable contract-validation records."""

    __slots__ = ()
