"""OCRLanguageResourceIdentity OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr.resource_identity_kind import (
    OCRResourceIdentityKind,
)


@dataclass(frozen=True)
class OCRLanguageResourceIdentity(AbstractIdentity):
    """One semantic language's selected backend resource identity."""

    language: str
    resource_name: str
    identity_kind: OCRResourceIdentityKind
    resource_identity: str

    def __post_init__(self) -> None:
        canonical_language = primitives._canonical_language_tag(self.language)
        object.__setattr__(self, "language", canonical_language)
        primitives._hard_bounded_string(
            "language resource name", self.resource_name, nonempty=True
        )
        if not isinstance(self.identity_kind, OCRResourceIdentityKind):
            raise ValueError("language resource identity kind is unsupported")
        primitives._hard_bounded_string(
            "language resource identity",
            self.resource_identity,
            nonempty=True,
        )
        if self.identity_kind is OCRResourceIdentityKind.SHA256:
            primitives._validate_sha256(
                "language resource identity", self.resource_identity
            )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.language,
            self.resource_name,
            self.identity_kind.value,
            self.resource_identity,
        )
