"""Explicit immutable targets accepted by ingestion materializers."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.identity import AbstractIdentity


class AbstractMaterializationTarget(AbstractIdentity, ABC):
    """Identify one exact external resource receiving a projection.

    Attributes
    ----------
    target_id
        Globally unambiguous stable identity of the external resource.
    schema_id
        Logical projection schema accepted by that resource slot.

    Notes
    -----
    A target identity names a resource; it does not grant permission to write
    it. Authority is bound separately in ``MaterializationRequest``.
    """

    __slots__ = ()

    target_id: str
    schema_id: str
