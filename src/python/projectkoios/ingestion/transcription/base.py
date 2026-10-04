from __future__ import annotations

import math
import re
from dataclasses import fields, is_dataclass
from enum import Enum
from re import Pattern
from typing import ClassVar

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.models import (
    ExtractedDocument,
    IngestionWarning,
    Metadata,
    SourceSpan,
)
from projectkoios.ingestion.transcription.configuration.error import (
    TranscriptionLimitError,
)


class AbstractTranscriptionDataObject(AbstractImmutableDataObject):
    """Nominal root and invariant owner for transcription data objects."""

    __slots__ = ()

    CONTRACT_NAME: ClassVar[str] = "structured-transcription"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    COMPOSER_VERSION: ClassVar[str] = "1"
    CONFIGURATION_VERSION: ClassVar[str] = "1"
    NORMALIZATION_METHOD: ClassVar[str] = "collapse_unicode_whitespace_v1"
    WHITESPACE: ClassVar[Pattern[str]] = re.compile(r"\s+")

    MAX_INPUT_BLOCKS: ClassVar[int] = 65_536
    MAX_INPUT_NODES: ClassVar[int] = 16_384
    MAX_TYPED_OBJECTS: ClassVar[int] = 16_384
    MAX_ITEMS: ClassVar[int] = 65_536
    MAX_OMISSIONS: ClassVar[int] = 65_536
    MAX_WARNINGS: ClassVar[int] = 16_384
    MAX_SOURCE_SPANS: ClassVar[int] = 262_144
    MAX_TEXT_CHARACTERS_PER_ITEM: ClassVar[int] = 1_000_000
    MAX_TOTAL_TEXT_CHARACTERS: ClassVar[int] = 10_000_000
    MAX_INPUT_ARTIFACT_BYTES: ClassVar[int] = 100_000_000
    MAX_RESULT_BYTES: ClassVar[int] = 128_000_000
    MAX_IDENTITY_CHARACTERS: ClassVar[int] = 4_096
    MAX_EVIDENCE_ENTRIES: ClassVar[int] = 256
    MAX_EVIDENCE_CHARACTERS: ClassVar[int] = 1_000_000

    @classmethod
    def normalize_text(cls, source_texts: tuple[str, ...]) -> str:
        return cls.WHITESPACE.sub(" ", "\n".join(source_texts)).strip()

    @classmethod
    def validate_exact_source_spans(
        cls, spans: tuple[SourceSpan, ...], document: ExtractedDocument
    ) -> None:
        cls.validate_source_spans(spans)
        page_by_index = {page.page_index: page for page in document.pages}
        for span in spans:
            if span.source_id != document.source.source_id or (
                span.source_blob_id != document.source.blob_id
            ):
                raise ValueError("transcription span refers to another source")
            page = page_by_index.get(span.page_index)
            if page is None:
                raise ValueError("transcription span page is unresolved")
            if span.printed_page_label is not None and (
                span.printed_page_label != page.printed_page_label
            ):
                raise ValueError(
                    "transcription span printed page label is stale"
                )
            if span.bounding_box is not None:
                x0, y0, x1, y1 = span.bounding_box
                if any(not math.isfinite(value) for value in span.bounding_box):
                    raise ValueError(
                        "transcription span geometry must be finite"
                    )
                if x0 < 0 or y0 < 0 or x1 > page.width or y1 > page.height:
                    raise ValueError(
                        "transcription span exceeds its source page"
                    )

    @classmethod
    def deduplicate_warnings(
        cls,
        warnings: tuple[IngestionWarning, ...],
    ) -> tuple[IngestionWarning, ...]:
        result: list[IngestionWarning] = []
        seen: set[str] = set()
        for warning in warnings:
            if warning.warning_id not in seen:
                seen.add(warning.warning_id)
                result.append(warning)
        return tuple(result)

    @classmethod
    def deduplicate_spans(
        cls,
        spans: tuple[SourceSpan, ...],
    ) -> tuple[SourceSpan, ...]:
        result: list[SourceSpan] = []
        seen: set[tuple[object, ...]] = set()
        for span in spans:
            identity = cls.source_span_identity_parts(span)
            if identity not in seen:
                seen.add(identity)
                result.append(span)
        return tuple(result)

    @classmethod
    def deduplicate_strings(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))

    @classmethod
    def source_span_identity_parts(cls, span: SourceSpan) -> tuple[object, ...]:
        return span.identity_parts() + (span.printed_page_label,)

    @classmethod
    def validate_source_spans(cls, spans: tuple[SourceSpan, ...]) -> None:
        cls.validate_tuple("source spans", spans)
        if any(not isinstance(span, SourceSpan) for span in spans):
            raise TypeError("source spans contain an unsupported value")
        identities = tuple(
            cls.source_span_identity_parts(span) for span in spans
        )
        if len(set(identities)) != len(identities):
            raise ValueError("source spans must be unique")

    @classmethod
    def validate_metadata(cls, value: Metadata) -> None:
        cls.validate_tuple("metadata", value)
        if len(value) > cls.MAX_EVIDENCE_ENTRIES:
            raise TranscriptionLimitError("too many metadata entries")
        total = 0
        for entry in value:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError("metadata must contain immutable pairs")
            key, item = entry
            cls.validate_bounded_string("metadata key", key, nonempty=True)
            cls.validate_bounded_string("metadata value", item)
            total += len(key) + len(item)
        if total > cls.MAX_EVIDENCE_CHARACTERS:
            raise TranscriptionLimitError("metadata exceeds its hard limit")

    @classmethod
    def validate_identity_fields(cls, *values: str) -> None:
        for value in values:
            cls.validate_bounded_string("identity field", value, nonempty=True)

    @classmethod
    def validate_unique_strings(
        cls, name: str, values: tuple[str, ...]
    ) -> None:
        cls.validate_tuple(name, values)
        for value in values:
            cls.validate_bounded_string(name, value, nonempty=True)
        if len(set(values)) != len(values):
            raise ValueError(f"{name} must be unique")

    @classmethod
    def validate_tuple(cls, name: str, value: object) -> None:
        if not isinstance(value, tuple):
            raise TypeError(f"{name} must be an immutable tuple")

    @classmethod
    def validate_bounded_string(
        cls,
        name: str,
        value: object,
        *,
        nonempty: bool = False,
        limit: int | None = None,
    ) -> None:
        if limit is None:
            limit = cls.MAX_IDENTITY_CHARACTERS
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if nonempty and not value:
            raise ValueError(f"{name} must be non-empty")
        if len(value) > limit:
            raise TranscriptionLimitError(f"{name} exceeds its hard limit")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError(f"{name} must be valid UTF-8") from error

    @classmethod
    def validate_positive_integer(cls, name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

    @classmethod
    def validate_nonnegative_integer(cls, name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    @classmethod
    def validate_unit_float(cls, name: str, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
        result = float(value)
        if not math.isfinite(result) or not 0.0 <= result <= 1.0:
            raise ValueError(f"{name} must be finite and within [0, 1]")
        return 0.0 if result == 0.0 else result

    @classmethod
    def validate_retained_size(cls, value: object, limit: int) -> None:
        total = 0
        stack = [value]
        seen: set[int] = set()
        while stack:
            item = stack.pop()
            if item is None or isinstance(item, (bool, int, float, Enum)):
                total += 16
            elif isinstance(item, str):
                total += len(item.encode("utf-8")) + 8
            elif isinstance(item, bytes):
                total += len(item)
            elif isinstance(item, tuple):
                marker = id(item)
                if marker in seen:
                    continue
                seen.add(marker)
                total += 8 * len(item)
                stack.extend(item)
            elif is_dataclass(item) and not isinstance(item, type):
                marker = id(item)
                if marker in seen:
                    continue
                seen.add(marker)
                for field in fields(item):
                    total += len(field.name) + 3
                    if field.name in ("content", "mask_content") and (
                        item.__class__.__name__
                        in ("RenderedRegion", "EmbeddedFigureArtifact")
                    ):
                        continue
                    stack.append(getattr(item, field.name))
            else:
                raise TypeError("transcription contains unsupported evidence")
            if total > limit:
                raise TranscriptionLimitError(
                    "transcription result exceeds max_result_bytes"
                )
