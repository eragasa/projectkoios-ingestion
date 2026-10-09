"""Replication and agreement policy for model annotation evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.model.configuration import (
    MAX_LAYOUT_MODEL_REPLICAS,
)


@dataclass(frozen=True, slots=True)
class LayoutModelAnnotationResolutionPolicy(AbstractImmutableDataObject):
    """Require replicated responses and bounded exact-candidate agreement."""

    CONTRACT_NAME: ClassVar[str] = "layout-model-annotation-resolution-policy"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    required_response_count: int = 3
    minimum_agreement_count: int = 2
    policy_id: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("required_response_count", "minimum_agreement_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
        if not 2 <= self.required_response_count <= MAX_LAYOUT_MODEL_REPLICAS:
            raise ValueError("required_response_count must be between 2 and 16")
        if (
            not 2
            <= self.minimum_agreement_count
            <= self.required_response_count
        ):
            raise ValueError(
                "minimum_agreement_count must be at least two and no greater "
                "than required_response_count"
            )
        object.__setattr__(
            self,
            "policy_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.required_response_count,
                self.minimum_agreement_count,
            ),
        )
