"""Trusted runtime configuration for durable page-projection publication."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.publication.status import (
    PageProjectionPublicationProfile,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationConfiguration:
    """Own trusted ceilings, authority, and the fixed publication profile."""

    profile: PageProjectionPublicationProfile
    authority_id: str
    maximum_source_bytes: int = 512_000_000
    maximum_page_count: int = 20_000
    maximum_block_count: int = 1_000_000
    maximum_payload_bytes: int = 1_000_000_000
    stream_chunk_bytes: int = 1_048_576
    low_text_character_threshold: int = 40

    def __post_init__(self) -> None:
        if not isinstance(self.profile, PageProjectionPublicationProfile):
            raise TypeError("profile must be a publication profile")
        if type(self.authority_id) is not str or not self.authority_id:
            raise ValueError("authority_id must be non-empty")
        if len(self.authority_id.encode("utf-8", errors="strict")) > 512:
            raise ValueError("authority_id exceeds its limit")
        bounds = (
            (
                self.maximum_source_bytes,
                MANAGED_ARTIFACT_LIMITS.maximum_artifact_bytes,
                "maximum_source_bytes",
            ),
            (
                self.maximum_page_count,
                min(
                    READING_EVIDENCE_LIMITS.maximum_pages,
                    PAGE_PROJECTION_LIMITS.maximum_pages,
                ),
                "maximum_page_count",
            ),
            (
                self.maximum_block_count,
                min(
                    READING_EVIDENCE_LIMITS.maximum_blocks,
                    PAGE_PROJECTION_LIMITS.maximum_blocks,
                ),
                "maximum_block_count",
            ),
            (
                self.maximum_payload_bytes,
                1_000_000_000,
                "maximum_payload_bytes",
            ),
            (
                self.stream_chunk_bytes,
                MANAGED_ARTIFACT_LIMITS.maximum_stream_chunk_bytes,
                "stream_chunk_bytes",
            ),
            (
                self.low_text_character_threshold,
                10_000_000,
                "low_text_character_threshold",
            ),
        )
        for value, maximum, name in bounds:
            minimum = 0 if name == "low_text_character_threshold" else 1
            if type(value) is not int or value < minimum or value > maximum:
                raise ValueError(f"{name} is outside its supported bound")
