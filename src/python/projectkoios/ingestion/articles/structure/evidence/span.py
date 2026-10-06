"""Article-structure evidence span."""

from __future__ import annotations

from collections.abc import Iterable

from projectkoios.ingestion.models import (
    SourceSpan,
)


def _ordered_unique_spans(
    values: Iterable[SourceSpan],
) -> tuple[SourceSpan, ...]:
    spans: list[SourceSpan] = []
    identities: set[tuple[object, ...]] = set()
    for value in values:
        if not isinstance(value, SourceSpan):
            raise TypeError(
                "structure span evidence must contain SourceSpan values"
            )
        identity = value.identity_parts()
        if identity in identities:
            continue
        identities.add(identity)
        spans.append(value)
    return tuple(spans)
