"""Provider-neutral model and runtime resource identity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class LayoutAnnotationModelResource(AbstractImmutableDataObject):
    """Bind one model invocation to exact model and runtime resources."""

    CONTRACT_NAME: ClassVar[str] = "layout-annotation-model-resource"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    provider_name: str
    model_name: str
    model_version: str
    model_sha256: SHA256Hash
    runtime_name: str
    runtime_version: str
    resource_id: str = field(init=False)

    def __post_init__(self) -> None:
        values = tuple(
            LayoutValueValidation.require_text(name, getattr(self, name))
            for name in (
                "provider_name",
                "model_name",
                "model_version",
                "runtime_name",
                "runtime_version",
            )
        )
        if not SHA256Hash.is_canonical(self.model_sha256):
            raise ValueError("model_sha256 must be a canonical SHA-256 digest")
        digest = SHA256Hash(self.model_sha256)
        object.__setattr__(self, "model_sha256", digest)
        object.__setattr__(
            self,
            "resource_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                values,
                digest,
            ),
        )
