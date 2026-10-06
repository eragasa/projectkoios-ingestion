"""Exact vendor-neutral equation-recognition processor identity."""

from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.ingestion.equations.recognition.resource import (
    EquationRecognitionResource,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True)
class EquationRecognitionProcessorIdentity:
    """Executable, resources, backend, and configuration of a recognizer."""

    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    executable_sha256: str
    executable_semantic_sha256: str
    resources: tuple[EquationRecognitionResource, ...]
    temperature: float

    @property
    def identity_digest(self) -> str:
        return stable_id(
            "equation-recognition-processor",
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            self.executable_semantic_sha256,
            self.resources,
            self.temperature,
        )

    def __post_init__(self) -> None:
        if not all(
            (
                self.processor_name,
                self.processor_version,
                self.backend_name,
                self.backend_version,
            )
        ):
            raise ValueError("recognition processor identity must be complete")
        if not SHA256Hash.is_canonical(self.executable_sha256):
            raise ValueError("recognition executable hash must be SHA-256")
        if not SHA256Hash.is_canonical(self.executable_semantic_sha256):
            raise ValueError(
                "recognition executable semantic hash must be SHA-256"
            )
        names = tuple(item.name for item in self.resources)
        if (
            not names
            or names != tuple(sorted(names))
            or len(names) != len(set(names))
        ):
            raise ValueError(
                "recognition resources must be non-empty, unique, and sorted"
            )
        if (
            not math.isfinite(self.temperature)
            or not 0.0 < self.temperature <= 1.0
        ):
            raise ValueError("recognition temperature must be in (0, 1]")
