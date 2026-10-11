from __future__ import annotations


class EvidenceFacade:
    def load(self, *, identity: str) -> str:
        return identity

    def publish(self, *, identity: str) -> str:
        return identity
