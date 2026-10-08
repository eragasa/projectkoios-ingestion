"""Immutable semantic reference topic-anchor inventories."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.reference.page.location.anchor import (
    ReferenceMatchTokenSequence,
    ReferenceTopicAnchor,
)
from projectkoios.ingestion.reference.page.location.limits.definition import (
    REFERENCE_LOCATOR_MAX_ANCHORS,
)
from projectkoios.ingestion.reference.page.location.limits.error import (
    ReferenceLocatorLimitError,
)

_ANCHOR_ID = re.compile(r"reference-topic-anchor:sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True, init=False)
class ReferenceTopicAnchorIdentityInventory:
    """One sorted, unique, bounded collection of anchor identities."""

    _identities: tuple[str, ...] = field(repr=True)

    def __init__(self, *identities: str) -> None:
        values = tuple(identities)
        if (
            values != tuple(sorted(values))
            or len(values) != len(set(values))
            or any(
                type(value) is not str or _ANCHOR_ID.fullmatch(value) is None
                for value in values
            )
        ):
            raise ValueError(
                "anchor identities must be sorted, unique, and valid"
            )
        if len(values) > REFERENCE_LOCATOR_MAX_ANCHORS:
            raise ReferenceLocatorLimitError(
                "topic anchor identity count exceeds limit"
            )
        object.__setattr__(self, "_identities", values)

    def __bool__(self) -> bool:
        return bool(self._identities)

    def __iter__(self) -> Iterator[str]:
        return iter(self._identities)

    def __len__(self) -> int:
        return len(self._identities)


@dataclass(frozen=True, slots=True, init=False)
class ReferenceTopicAnchorInventory:
    """One sorted, unique, bounded collection of semantic anchors."""

    _anchors: tuple[ReferenceTopicAnchor, ...] = field(repr=True)

    def __init__(self, *anchors: ReferenceTopicAnchor) -> None:
        values = tuple(anchors)
        if not values:
            raise ValueError("topic anchor inventory must not be empty")
        if len(values) > REFERENCE_LOCATOR_MAX_ANCHORS:
            raise ReferenceLocatorLimitError("topic anchor count exceeds limit")
        if any(type(anchor) is not ReferenceTopicAnchor for anchor in values):
            raise TypeError(
                "topic anchor inventory requires ReferenceTopicAnchor values"
            )
        texts = tuple(anchor.text for anchor in values)
        if texts != tuple(sorted(texts)) or len(texts) != len(set(texts)):
            raise ValueError("topic anchors must be sorted and unique")
        normalized = tuple(anchor.normalized_tokens for anchor in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("normalized topic anchors must be unique")
        object.__setattr__(self, "_anchors", values)

    def __iter__(self) -> Iterator[ReferenceTopicAnchor]:
        return iter(self._anchors)

    def __len__(self) -> int:
        return len(self._anchors)

    def match(self, page_text: str) -> ReferenceTopicAnchorMatch:
        """Partition anchor identities by complete phrase occurrence."""
        page_tokens = ReferenceMatchTokenSequence(page_text)
        matched_values: list[str] = []
        unmatched_values: list[str] = []
        for anchor in self._anchors:
            destination = (
                matched_values
                if anchor.matches(page_tokens)
                else unmatched_values
            )
            destination.append(anchor.anchor_id)
        matched = tuple(sorted(matched_values))
        unmatched = tuple(sorted(unmatched_values))
        return ReferenceTopicAnchorMatch(
            all_identities=ReferenceTopicAnchorIdentityInventory(
                *sorted(anchor.anchor_id for anchor in self._anchors)
            ),
            matched_identities=ReferenceTopicAnchorIdentityInventory(*matched),
            unmatched_identities=ReferenceTopicAnchorIdentityInventory(
                *unmatched
            ),
        )


@dataclass(frozen=True, slots=True)
class ReferenceTopicAnchorMatch:
    """Exact identity partition produced by one bounded anchor match."""

    all_identities: ReferenceTopicAnchorIdentityInventory
    matched_identities: ReferenceTopicAnchorIdentityInventory
    unmatched_identities: ReferenceTopicAnchorIdentityInventory

    def __post_init__(self) -> None:
        for name, value in (
            ("all_identities", self.all_identities),
            ("matched_identities", self.matched_identities),
            ("unmatched_identities", self.unmatched_identities),
        ):
            if type(value) is not ReferenceTopicAnchorIdentityInventory:
                raise TypeError(
                    f"{name} must be ReferenceTopicAnchorIdentityInventory"
                )
        if not self.all_identities:
            raise ValueError(
                "topic anchor identity inventory must not be empty"
            )
        matched = set(self.matched_identities)
        unmatched = set(self.unmatched_identities)
        if matched & unmatched:
            raise ValueError("matched and unmatched anchors must be disjoint")
        if tuple(sorted(matched | unmatched)) != tuple(self.all_identities):
            raise ValueError("match must partition topic anchor identities")
