"""Deterministic equation native-text sanitization."""

from __future__ import annotations

import unicodedata


def sanitize_equation_native_text(value: str) -> tuple[str, int]:
    """Replace controls deterministically while retaining a change count."""

    output: list[str] = []
    count = 0
    for character in value:
        if unicodedata.category(character) == "Cc":
            count += 1
            output.append(" " if character in "\n\r\t" else "�")
        else:
            output.append(character)
    return " ".join("".join(output).split()), count
