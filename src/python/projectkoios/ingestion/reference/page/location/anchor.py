"""Immutable bounded reference topic-anchor values."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.reference.page.location.definition import (
    REFERENCE_LOCATOR_CONTRACT_VERSION,
)
from projectkoios.ingestion.reference.page.location.limits.definition import (
    REFERENCE_LOCATOR_MAX_ANCHOR_CHARACTERS,
    REFERENCE_LOCATOR_MAX_ANCHOR_TOKENS,
    REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS,
)
from projectkoios.ingestion.reference.page.location.limits.error import (
    ReferenceLocatorLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReferenceMatchTokenSequence:
    """Immutable NFKC case-folded alphanumeric token sequence."""

    _values: tuple[str, ...] = field(repr=False)

    def __init__(self, text: str) -> None:
        if type(text) is not str:
            raise TypeError("match text must be a built-in string")
        if len(text) > REFERENCE_LOCATOR_MAX_PAGE_CHARACTERS:
            raise ReferenceLocatorLimitError("match text exceeds text limit")
        try:
            text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError("match text must be valid UTF-8") from error
        normalized = unicodedata.normalize("NFKC", text).casefold()
        tokens: list[str] = []
        current: list[str] = []
        for character in normalized:
            if character.isalnum():
                current.append(character)
            elif current:
                tokens.append("".join(current))
                current = []
        if current:
            tokens.append("".join(current))
        object.__setattr__(self, "_values", tuple(tokens))

    def __bool__(self) -> bool:
        return bool(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def contains(self, needle: ReferenceMatchTokenSequence) -> bool:
        """Return whether a complete token sequence occurs contiguously."""
        needle_values = needle._values
        if not needle_values or len(needle_values) > len(self._values):
            return False
        return any(
            self._values[index : index + len(needle_values)] == needle_values
            for index in range(len(self._values) - len(needle_values) + 1)
        )


@dataclass(frozen=True, slots=True)
class ReferenceTopicAnchor:
    """One bounded normalized topic anchor and its stable identity."""

    text: str
    anchor_id: str = field(init=False)
    _tokens: ReferenceMatchTokenSequence = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.text) is not str:
            raise TypeError("topic anchor must be a built-in string")
        if not self.text or self.text.strip() != self.text:
            raise ValueError("topic anchor must be nonempty and trimmed")
        if len(self.text) > REFERENCE_LOCATOR_MAX_ANCHOR_CHARACTERS:
            raise ReferenceLocatorLimitError("topic anchor exceeds text limit")
        tokens = ReferenceMatchTokenSequence(self.text)
        if not tokens:
            raise ValueError("topic anchor must contain alphanumeric tokens")
        if len(tokens) > REFERENCE_LOCATOR_MAX_ANCHOR_TOKENS:
            raise ReferenceLocatorLimitError("topic anchor exceeds token limit")
        object.__setattr__(self, "_tokens", tokens)
        object.__setattr__(
            self,
            "anchor_id",
            stable_id(
                "reference-topic-anchor",
                tokens._values,
                REFERENCE_LOCATOR_CONTRACT_VERSION,
            ),
        )

    @property
    def normalized_tokens(self) -> ReferenceMatchTokenSequence:
        """Return the normalized token value for inventory comparison."""
        return self._tokens

    def matches(self, page_tokens: ReferenceMatchTokenSequence) -> bool:
        """Return whether this complete anchor phrase occurs on a page."""
        return page_tokens.contains(self._tokens)
