"""Article-structure normalization text."""

from __future__ import annotations

import unicodedata


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
