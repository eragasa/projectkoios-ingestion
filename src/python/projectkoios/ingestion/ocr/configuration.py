"""OCRConfiguration OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr._limits import (
    _MAX_BYTES_PER_IMAGE,
    _MAX_IDENTITY_FIELD_CHARACTERS,
    _MAX_IMAGES,
    _MAX_LANGUAGE_CHARACTERS,
    _MAX_LANGUAGES,
    _MAX_LINES_PER_SELECTION,
    _MAX_PIXELS_PER_IMAGE,
    _MAX_RESULT_BYTES,
    _MAX_SELECTIONS,
    _MAX_TEXT_CHARACTERS_PER_ITEM,
    _MAX_TEXT_CHARACTERS_PER_SELECTION,
    _MAX_TOKENS_PER_SELECTION,
    _MAX_TOTAL_IDENTITY_CHARACTERS,
    _MAX_TOTAL_IMAGE_BYTES,
    _MAX_TOTAL_LINES,
    _MAX_TOTAL_PIXELS,
    _MAX_TOTAL_TEXT_CHARACTERS,
    _MAX_TOTAL_TOKENS,
    _MAX_TOTAL_WARNINGS,
    _MAX_WARNING_EVIDENCE_ENTRIES,
    _MAX_WARNING_MESSAGE_CHARACTERS,
    _MAX_WARNINGS_PER_SELECTION,
)
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError
from projectkoios.ingestion.ocr.output_mode import OCROutputMode


@dataclass(frozen=True)
class OCRConfiguration(AbstractImmutableDataObject):
    """Language/output choices and deterministic OCR resource limits."""

    languages: tuple[str, ...] = ("und",)
    output_mode: OCROutputMode = OCROutputMode.TOKENS_AND_LINES
    max_selections: int = _MAX_SELECTIONS
    max_images: int = _MAX_IMAGES
    max_pixels_per_image: int = _MAX_PIXELS_PER_IMAGE
    max_bytes_per_image: int = _MAX_BYTES_PER_IMAGE
    max_total_pixels: int = _MAX_TOTAL_PIXELS
    max_total_image_bytes: int = _MAX_TOTAL_IMAGE_BYTES
    max_languages: int = _MAX_LANGUAGES
    max_language_characters: int = _MAX_LANGUAGE_CHARACTERS
    max_identity_field_characters: int = _MAX_IDENTITY_FIELD_CHARACTERS
    max_total_identity_characters: int = _MAX_TOTAL_IDENTITY_CHARACTERS
    max_tokens_per_selection: int = _MAX_TOKENS_PER_SELECTION
    max_lines_per_selection: int = _MAX_LINES_PER_SELECTION
    max_text_characters_per_item: int = _MAX_TEXT_CHARACTERS_PER_ITEM
    max_text_characters_per_selection: int = _MAX_TEXT_CHARACTERS_PER_SELECTION
    max_warnings_per_selection: int = _MAX_WARNINGS_PER_SELECTION
    max_warning_message_characters: int = _MAX_WARNING_MESSAGE_CHARACTERS
    max_warning_evidence_entries: int = _MAX_WARNING_EVIDENCE_ENTRIES
    max_total_tokens: int = _MAX_TOTAL_TOKENS
    max_total_lines: int = _MAX_TOTAL_LINES
    max_total_text_characters: int = _MAX_TOTAL_TEXT_CHARACTERS
    max_total_warnings: int = _MAX_TOTAL_WARNINGS
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        primitives._require_tuple("languages", self.languages)
        integer_fields = (
            ("max_selections", _MAX_SELECTIONS),
            ("max_images", _MAX_IMAGES),
            ("max_pixels_per_image", _MAX_PIXELS_PER_IMAGE),
            ("max_bytes_per_image", _MAX_BYTES_PER_IMAGE),
            ("max_total_pixels", _MAX_TOTAL_PIXELS),
            ("max_total_image_bytes", _MAX_TOTAL_IMAGE_BYTES),
            ("max_languages", _MAX_LANGUAGES),
            ("max_language_characters", _MAX_LANGUAGE_CHARACTERS),
            (
                "max_identity_field_characters",
                _MAX_IDENTITY_FIELD_CHARACTERS,
            ),
            (
                "max_total_identity_characters",
                _MAX_TOTAL_IDENTITY_CHARACTERS,
            ),
            ("max_tokens_per_selection", _MAX_TOKENS_PER_SELECTION),
            ("max_lines_per_selection", _MAX_LINES_PER_SELECTION),
            (
                "max_text_characters_per_item",
                _MAX_TEXT_CHARACTERS_PER_ITEM,
            ),
            (
                "max_text_characters_per_selection",
                _MAX_TEXT_CHARACTERS_PER_SELECTION,
            ),
            ("max_warnings_per_selection", _MAX_WARNINGS_PER_SELECTION),
            (
                "max_warning_message_characters",
                _MAX_WARNING_MESSAGE_CHARACTERS,
            ),
            (
                "max_warning_evidence_entries",
                _MAX_WARNING_EVIDENCE_ENTRIES,
            ),
            ("max_total_tokens", _MAX_TOTAL_TOKENS),
            ("max_total_lines", _MAX_TOTAL_LINES),
            (
                "max_total_text_characters",
                _MAX_TOTAL_TEXT_CHARACTERS,
            ),
            ("max_total_warnings", _MAX_TOTAL_WARNINGS),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        )
        for name, hard_maximum in integer_fields:
            value = getattr(self, name)
            primitives._positive_integer(name, value)
            if value > hard_maximum:
                raise OCRContractLimitError(
                    f"{name} exceeds the implementation maximum "
                    f"({hard_maximum})"
                )
        if len(self.languages) > self.max_languages:
            raise OCRContractLimitError("language count exceeds max_languages")
        if not self.languages:
            raise ValueError("languages must be non-empty and unique")
        normalized_languages = tuple(
            primitives._canonical_language_tag(language)
            for language in self.languages
        )
        if any(
            len(language) > self.max_language_characters
            for language in normalized_languages
        ):
            raise OCRContractLimitError("language exceeds its configured limit")
        if len(set(normalized_languages)) != len(normalized_languages):
            raise ValueError(
                "languages must be unique after BCP 47 canonicalization"
            )
        object.__setattr__(self, "languages", normalized_languages)
        if not isinstance(self.output_mode, OCROutputMode):
            raise ValueError("output_mode must be an OCROutputMode")

    @property
    def configuration_digest(self) -> str:
        return stable_id("ocr-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name).value)
            if name == "output_mode"
            else (name, getattr(self, name))
            for name in self.__dataclass_fields__
        )
