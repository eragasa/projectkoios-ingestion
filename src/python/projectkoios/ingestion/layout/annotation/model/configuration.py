"""Bounded model invocation configuration."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

MAX_LAYOUT_MODEL_RESPONSE_BYTES = 2_000_000
MAX_LAYOUT_MODEL_SEED = 2**63 - 1
MAX_LAYOUT_MODEL_REPLICAS = 16


@dataclass(frozen=True, slots=True)
class LayoutAnnotationModelConfiguration(AbstractImmutableDataObject):
    """Bind sampling and response bounds without provider-specific values."""

    CONTRACT_NAME: ClassVar[str] = "layout-annotation-model-configuration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    temperature: float = 0.0
    seed: int = 0
    maximum_response_bytes: int = 256_000
    configuration_id: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.temperature, bool)
            or not isinstance(self.temperature, int | float)
            or not math.isfinite(float(self.temperature))
            or not 0.0 <= float(self.temperature) <= 2.0
        ):
            raise ValueError(
                "temperature must be finite and between zero and two"
            )
        temperature = float(self.temperature)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not 0 <= self.seed <= MAX_LAYOUT_MODEL_SEED:
            raise ValueError("seed is outside the supported range")
        if (
            isinstance(self.maximum_response_bytes, bool)
            or not isinstance(self.maximum_response_bytes, int)
            or not 1
            <= self.maximum_response_bytes
            <= MAX_LAYOUT_MODEL_RESPONSE_BYTES
        ):
            raise ValueError("maximum_response_bytes is outside its limit")
        object.__setattr__(self, "temperature", temperature)
        object.__setattr__(
            self,
            "configuration_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                temperature,
                self.seed,
                self.maximum_response_bytes,
            ),
        )
