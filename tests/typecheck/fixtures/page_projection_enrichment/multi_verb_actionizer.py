from __future__ import annotations

from projectkoios.base import DataObjectActionizer


class MultiVerbActionizer(DataObjectActionizer[object, object]):
    def action(self, *, request: object) -> object:
        return request

    def publish(self, *, request: object) -> object:
        return request
