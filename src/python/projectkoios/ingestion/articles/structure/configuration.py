"""Article-structure configuration."""

from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.ingestion.articles.structure.limits.definition import (
    _MAX_ABSTRACT_BLOCKS,
    _MAX_BIBLIOGRAPHY_ENTRIES,
    _MAX_HEADING_CHARACTERS,
    _MAX_INPUT_BLOCKS,
    _MAX_NODES,
    _MAX_PAGES,
    _MAX_TEXT_BLOCKS,
    _MAX_TEXT_CHARACTERS,
    _MAX_WARNINGS,
)
from projectkoios.ingestion.articles.structure.limits.error import (
    ArticleStructureLimitError,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True)
class ArticleStructureConfiguration:
    max_pages: int = _MAX_PAGES
    max_input_blocks: int = _MAX_INPUT_BLOCKS
    max_text_blocks: int = _MAX_TEXT_BLOCKS
    max_nodes: int = _MAX_NODES
    max_warnings: int = _MAX_WARNINGS
    max_text_characters: int = _MAX_TEXT_CHARACTERS
    max_heading_characters: int = _MAX_HEADING_CHARACTERS
    max_abstract_blocks: int = _MAX_ABSTRACT_BLOCKS
    max_bibliography_entries: int = _MAX_BIBLIOGRAPHY_ENTRIES
    fallback_title_top_ratio: float = 0.3

    def __post_init__(self) -> None:
        for name, maximum in (
            ("max_pages", _MAX_PAGES),
            ("max_input_blocks", _MAX_INPUT_BLOCKS),
            ("max_text_blocks", _MAX_TEXT_BLOCKS),
            ("max_nodes", _MAX_NODES),
            ("max_warnings", _MAX_WARNINGS),
            ("max_text_characters", _MAX_TEXT_CHARACTERS),
            ("max_heading_characters", _MAX_HEADING_CHARACTERS),
            ("max_abstract_blocks", _MAX_ABSTRACT_BLOCKS),
            ("max_bibliography_entries", _MAX_BIBLIOGRAPHY_ENTRIES),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
            if value > maximum:
                raise ArticleStructureLimitError(
                    f"{name} exceeds the implementation maximum ({maximum})"
                )
        ratio = self.fallback_title_top_ratio
        if isinstance(ratio, bool) or not isinstance(ratio, int | float):
            raise ValueError("fallback_title_top_ratio must be finite")
        normalized = float(ratio)
        if not math.isfinite(normalized) or not 0.0 < normalized <= 1.0:
            raise ValueError(
                "fallback_title_top_ratio must be greater than zero and "
                "no greater than one"
            )
        object.__setattr__(self, "fallback_title_top_ratio", normalized)

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "article-structure-configuration",
            self.max_pages,
            self.max_input_blocks,
            self.max_text_blocks,
            self.max_nodes,
            self.max_warnings,
            self.max_text_characters,
            self.max_heading_characters,
            self.max_abstract_blocks,
            self.max_bibliography_entries,
            self.fallback_title_top_ratio,
        )
