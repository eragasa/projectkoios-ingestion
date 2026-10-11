from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from projectkoios.base import DataObjectActionizer

NestedValues = tuple[str, tuple[int, tuple[str, ...]]]


def _normalize(values: NestedValues) -> NestedValues:
    return values


class FixtureStatus(StrEnum):
    READY = "ready"


@dataclass(frozen=True, slots=True)
class FixtureIdentity:
    value: str


class FixtureActionizer(DataObjectActionizer[FixtureIdentity, FixtureIdentity]):
    def action(self, *, request: FixtureIdentity) -> FixtureIdentity:
        return self._preserve(request=request)

    def _preserve(self, *, request: FixtureIdentity) -> FixtureIdentity:
        return request
