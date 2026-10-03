"""Backend-neutral PDF extraction configuration and limit contracts."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id

DEFAULT_MAXIMUM_PDF_PAGES = 10_000
_HARD_MAXIMUM_PDF_PAGES = 100_000


class PdfPageLimitError(ValueError):
    """Raised before page loading when a PDF exceeds the explicit page bound."""

    def __init__(self, *, page_count: int, maximum_pages: int) -> None:
        super().__init__(
            f"PDF page count {page_count} exceeds maximum_pages "
            f"({maximum_pages})"
        )
        self.page_count = page_count
        self.maximum_pages = maximum_pages


@dataclass(frozen=True)
class PdfExtractionConfiguration:
    """Deterministic backend-neutral PDF extraction configuration."""

    low_text_character_threshold: int = 40
    maximum_pages: int = DEFAULT_MAXIMUM_PDF_PAGES

    def __post_init__(self) -> None:
        for name, value, maximum in (
            (
                "low_text_character_threshold",
                self.low_text_character_threshold,
                10_000_000,
            ),
            ("maximum_pages", self.maximum_pages, _HARD_MAXIMUM_PDF_PAGES),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < (0 if name == "low_text_character_threshold" else 1)
                or value > maximum
            ):
                raise ValueError(
                    f"{name} must be within its supported integer bound"
                )

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "configuration",
            {
                "low_text_character_threshold": (
                    self.low_text_character_threshold
                ),
                "maximum_pages": self.maximum_pages,
            },
        )


__all__ = [
    "DEFAULT_MAXIMUM_PDF_PAGES",
    "PdfExtractionConfiguration",
    "PdfPageLimitError",
]
