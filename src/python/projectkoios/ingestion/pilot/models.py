from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import BaseDocument


@dataclass(frozen=True)
class PilotDocument(BaseDocument):
    pass
