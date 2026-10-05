"""Nominal result returned by configurable pipelines."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from projectkoios.base import DataObjectActionResult


class PipelineResult(DataObjectActionResult, ABC):
    """Require a named immutable result contract for pipeline identity."""

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str]
