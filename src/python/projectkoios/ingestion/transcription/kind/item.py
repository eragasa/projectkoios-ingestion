from __future__ import annotations

from enum import StrEnum


class TranscriptionItemKind(StrEnum):
    PAGE_ANCHOR = "page_anchor"
    HEADING = "heading"
    PROSE = "prose"
    EQUATION = "equation"
    TABLE = "table"
    FIGURE = "figure"
