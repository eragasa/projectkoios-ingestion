"""Immutable resource ceilings for pure page projection."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.limits.error import (
    PageProjectionLimitError,
)


@dataclass(frozen=True, slots=True)
class PageProjectionLimits:
    """Own fixed page, block, text, verification, work, and hash bounds."""

    maximum_pages: int = field(default=20_000, init=False)
    maximum_blocks: int = field(default=1_000_000, init=False)
    maximum_page_blocks: int = field(default=100_000, init=False)
    maximum_block_text_bytes: int = field(default=262_144, init=False)
    maximum_projected_text_bytes: int = field(
        default=1_073_741_824,
        init=False,
    )
    maximum_verification_evidence: int = field(default=4_096, init=False)
    maximum_observed_artifact_bytes: int = field(
        default=64_000_000_000,
        init=False,
    )
    maximum_total_work: int = field(default=2_024_096, init=False)
    maximum_identity_characters: int = field(default=1_024, init=False)
    maximum_processor_version_bytes: int = field(default=1_024, init=False)
    maximum_identity_input_bytes: int = field(default=16_777_216, init=False)

    def require_count(
        self,
        value: object,
        name: str,
        *,
        maximum: int,
    ) -> int:
        """Return one bounded nonnegative built-in count."""
        if type(value) is not int or value < 0:
            raise PageProjectionError(
                f"{name} must be a nonnegative built-in integer"
            )
        if value > maximum:
            raise PageProjectionLimitError(f"{name} exceeds its limit")
        return value

    def require_text(
        self,
        value: object,
        name: str,
        *,
        maximum_bytes: int,
    ) -> str:
        """Return one nonempty strictly encoded bounded string."""
        if type(value) is not str or not value:
            raise PageProjectionError(f"{name} must be a nonempty string")
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise PageProjectionError(f"{name} must be valid UTF-8") from error
        if len(encoded) > maximum_bytes:
            raise PageProjectionLimitError(f"{name} exceeds its limit")
        return value

    def require_identity(self, value: object, name: str) -> str:
        """Return one bounded nonempty identity string."""
        return self.require_text(
            value,
            name,
            maximum_bytes=self.maximum_identity_characters,
        )


PAGE_PROJECTION_LIMITS = PageProjectionLimits()
