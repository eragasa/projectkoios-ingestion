"""OCRProcessorIdentity OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr._limits import _MAX_LANGUAGES
from projectkoios.ingestion.ocr.language_resource_identity import (
    OCRLanguageResourceIdentity,
)
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.request import OCRRequest
from projectkoios.ingestion.base.identity import AbstractIdentity


@dataclass(frozen=True)
class OCRProcessorIdentity(AbstractIdentity):
    """Request-specific processor/backend and language-resource identity."""

    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    language_resources: tuple[OCRLanguageResourceIdentity, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("processor_name", self.processor_name),
            ("processor_version", self.processor_version),
            ("backend_name", self.backend_name),
            ("backend_version", self.backend_version),
        ):
            primitives._hard_bounded_string(name, value, nonempty=True)
        primitives._require_tuple("language_resources", self.language_resources)
        if len(self.language_resources) > _MAX_LANGUAGES:
            raise OCRContractLimitError("too many language resource bindings")
        for binding in self.language_resources:
            if not isinstance(binding, OCRLanguageResourceIdentity):
                raise TypeError(
                    "language_resources must contain resource identities"
                )
        languages = tuple(item.language for item in self.language_resources)
        if len(set(languages)) != len(languages):
            raise ValueError("language resource bindings must be unique")

    def validate_for(self, request: OCRRequest) -> None:
        languages = tuple(item.language for item in self.language_resources)
        if languages != request.configuration.languages:
            raise ValueError(
                "language resources must bind requested languages in order"
            )

    @property
    def identity_digest(self) -> str:
        return stable_id("ocr-processor-identity", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            tuple(item.identity_parts() for item in self.language_resources),
        )
