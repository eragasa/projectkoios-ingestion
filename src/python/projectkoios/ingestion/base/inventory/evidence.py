"""Immutable evidence returned by inventories."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


class AbstractInventoryEvidence(AbstractImmutableDataObject, ABC):
    """Require provenance and a digest for one observed inventory."""

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str]
    inventory_id: str
    target_id: str
    configuration_id: str
    authority_id: str
    canonical_sha256: str
