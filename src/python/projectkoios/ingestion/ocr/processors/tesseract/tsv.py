from __future__ import annotations

import math
import re

from projectkoios.ingestion.ocr.models import (
    OCRConfidence,
    OCRConfiguration,
    OCRContractLimitError,
    OCRLine,
    OCROutputMode,
    OcrProcessorIdentity,
    OCRSelection,
    OCRSelectionResult,
    OCRToken,
)
from projectkoios.ingestion.ocr.processors.tesseract.constants import (
    MAX_CAPTURE_BYTES,
    TESSERACT_TSV_HEADER,
)
from projectkoios.ingestion.ocr.processors.tesseract.identity import (
    TesseractIdentity,
)
from projectkoios.ingestion.ocr.processors.tesseract.models import (
    ParsedLine,
    ParsedWord,
)


class TesseractTsvParser:
    @staticmethod
    def exceeds_aggregate_limits(
        selection_results: tuple[OCRSelectionResult, ...],
        configuration: OCRConfiguration,
    ) -> bool:
        token_count = sum(len(item.tokens) for item in selection_results)
        line_count = sum(len(item.lines) for item in selection_results)
        warning_count = sum(len(item.warnings) for item in selection_results)
        text_characters = sum(
            sum(len(token.text) for token in item.tokens)
            + sum(len(line.text) for line in item.lines)
            for item in selection_results
        )
        return (
            token_count > configuration.max_total_tokens
            or line_count > configuration.max_total_lines
            or warning_count > configuration.max_total_warnings
            or text_characters > configuration.max_total_text_characters
        )

    @classmethod
    def build_outputs(
        cls,
        *,
        selection: OCRSelection,
        configuration: OCRConfiguration,
        identity: OcrProcessorIdentity,
        parsed_lines: tuple[ParsedLine, ...],
        warning_ids: tuple[str, ...],
    ) -> tuple[tuple[OCRToken, ...], tuple[OCRLine, ...]]:
        mode = configuration.output_mode
        include_tokens = mode in (
            OCROutputMode.TOKENS,
            OCROutputMode.TOKENS_AND_LINES,
        )
        include_lines = mode in (
            OCROutputMode.LINES,
            OCROutputMode.TOKENS_AND_LINES,
        )
        tokens: list[OCRToken] = []
        token_ids_by_line: list[tuple[str, ...]] = []
        token_order = 0
        for line_order, parsed_line in enumerate(parsed_lines):
            line_token_ids: list[str] = []
            if include_tokens:
                for word in parsed_line.words:
                    token = OCRToken.create(
                        selection=selection,
                        configuration=configuration,
                        text=word.text,
                        pixel_bounding_box=word.pixel_bounding_box,
                        confidence=cls._word_confidence(word.confidence),
                        order=token_order,
                        line_order=(
                            line_order
                            if mode is OCROutputMode.TOKENS_AND_LINES
                            else None
                        ),
                        warning_ids=warning_ids,
                        **TesseractIdentity.keywords(identity),
                    )
                    tokens.append(token)
                    line_token_ids.append(token.token_id)
                    token_order += 1
            token_ids_by_line.append(tuple(line_token_ids))

        lines: list[OCRLine] = []
        if include_lines:
            for order, parsed_line in enumerate(parsed_lines):
                lines.append(
                    OCRLine.create(
                        selection=selection,
                        configuration=configuration,
                        text=parsed_line.text,
                        pixel_bounding_box=parsed_line.pixel_bounding_box,
                        confidence=cls._line_confidence(parsed_line.confidence),
                        order=order,
                        token_ids=(
                            token_ids_by_line[order]
                            if mode is OCROutputMode.TOKENS_AND_LINES
                            else ()
                        ),
                        warning_ids=warning_ids,
                        **TesseractIdentity.keywords(identity),
                    )
                )
        return tuple(tokens), tuple(lines)

    @classmethod
    def parse(
        cls,
        payload: bytes,
        configuration: OCRConfiguration,
    ) -> tuple[ParsedLine, ...]:
        if len(payload) > MAX_CAPTURE_BYTES:
            raise OCRContractLimitError("TSV output exceeds the safety limit")
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ValueError("TSV output is not valid UTF-8") from error
        if "\x00" in text:
            raise ValueError("TSV output contains a NUL character")
        rows = text.splitlines()
        if not rows or rows[0] != TESSERACT_TSV_HEADER:
            raise ValueError("TSV output has an unsupported header")
        grouped: dict[tuple[int, int, int, int], list[ParsedWord]] = {}
        last_word_number: dict[tuple[int, int, int, int], int] = {}
        word_count = 0
        text_characters = 0
        for row_number, row in enumerate(rows[1:], start=2):
            if not row:
                continue
            columns = row.split("\t", 11)
            if len(columns) != 12:
                raise ValueError(
                    f"TSV row {row_number} has the wrong column count"
                )
            numeric = tuple(
                cls._tsv_integer(value, row_number) for value in columns[:10]
            )
            (
                level,
                page_number,
                block_number,
                paragraph_number,
                line_number,
                word_number,
                left,
                top,
                width,
                height,
            ) = numeric
            if level not in {1, 2, 3, 4, 5}:
                raise ValueError(
                    f"TSV row {row_number} has an unsupported level"
                )
            if page_number != 1:
                raise ValueError(f"TSV row {row_number} refers to another page")
            if level != 5:
                continue
            token_text = columns[11].strip()
            if not token_text:
                continue
            if (
                min(
                    block_number,
                    paragraph_number,
                    line_number,
                    word_number,
                )
                <= 0
            ):
                raise ValueError(
                    f"TSV row {row_number} has invalid word hierarchy"
                )
            line_key = (
                page_number,
                block_number,
                paragraph_number,
                line_number,
            )
            if word_number <= last_word_number.get(line_key, 0):
                raise ValueError(
                    f"TSV row {row_number} has duplicate or unordered words"
                )
            last_word_number[line_key] = word_number
            if width <= 0 or height <= 0:
                raise ValueError(f"TSV row {row_number} has an empty word box")
            word = ParsedWord(
                text=token_text,
                pixel_bounding_box=(
                    float(left),
                    float(top),
                    float(left + width),
                    float(top + height),
                ),
                confidence=cls._tsv_confidence(columns[10], row_number),
                line_key=line_key,
            )
            grouped.setdefault(word.line_key, []).append(word)
            word_count += 1
            text_characters += len(token_text)
            if word_count > configuration.max_tokens_per_selection:
                raise OCRContractLimitError(
                    "TSV token count exceeds max_tokens_per_selection"
                )
            if text_characters > (
                configuration.max_text_characters_per_selection
            ):
                raise OCRContractLimitError(
                    "TSV text exceeds max_text_characters_per_selection"
                )
        if len(grouped) > configuration.max_lines_per_selection:
            raise OCRContractLimitError(
                "TSV line count exceeds max_lines_per_selection"
            )
        parsed_lines: list[ParsedLine] = []
        line_text_characters = 0
        for words in grouped.values():
            line_text = " ".join(word.text for word in words)
            line_text_characters += len(line_text)
            confidences = tuple(word.confidence for word in words)
            line_confidence = (
                sum(value for value in confidences if value is not None)
                / len(confidences)
                if all(value is not None for value in confidences)
                else None
            )
            parsed_lines.append(
                ParsedLine(
                    text=line_text,
                    pixel_bounding_box=(
                        min(word.pixel_bounding_box[0] for word in words),
                        min(word.pixel_bounding_box[1] for word in words),
                        max(word.pixel_bounding_box[2] for word in words),
                        max(word.pixel_bounding_box[3] for word in words),
                    ),
                    confidence=line_confidence,
                    words=tuple(words),
                )
            )
        retained_text_characters = 0
        if configuration.output_mode in (
            OCROutputMode.TOKENS,
            OCROutputMode.TOKENS_AND_LINES,
        ):
            retained_text_characters += text_characters
        if configuration.output_mode in (
            OCROutputMode.LINES,
            OCROutputMode.TOKENS_AND_LINES,
        ):
            retained_text_characters += line_text_characters
        if retained_text_characters > (
            configuration.max_text_characters_per_selection
        ):
            raise OCRContractLimitError(
                "TSV text exceeds max_text_characters_per_selection"
            )
        return tuple(parsed_lines)

    @staticmethod
    def _word_confidence(value: float | None) -> OCRConfidence | None:
        if value is None:
            return None
        return OCRConfidence(
            value=value,
            method="tesseract-tsv-word-confidence",
            method_version="1",
            scale="tesseract_0_to_100_normalized_to_unit_interval",
        )

    @staticmethod
    def _line_confidence(value: float | None) -> OCRConfidence | None:
        if value is None:
            return None
        return OCRConfidence(
            value=value,
            method="tesseract-tsv-line-mean-word-confidence",
            method_version="1",
            scale="arithmetic_mean_of_normalized_word_scores",
        )

    @staticmethod
    def _tsv_integer(value: str, row_number: int) -> int:
        if not re.fullmatch(r"-?\d+", value):
            raise ValueError(
                f"TSV row {row_number} contains a non-integer field"
            )
        parsed = int(value)
        if parsed < 0:
            raise ValueError(f"TSV row {row_number} contains a negative field")
        return parsed

    @staticmethod
    def _tsv_confidence(value: str, row_number: int) -> float | None:
        try:
            parsed = float(value)
        except ValueError as error:
            raise ValueError(
                f"TSV row {row_number} has invalid confidence"
            ) from error
        if not math.isfinite(parsed):
            raise ValueError(f"TSV row {row_number} has invalid confidence")
        if parsed == -1.0:
            return None
        if not 0.0 <= parsed <= 100.0:
            raise ValueError(f"TSV row {row_number} has invalid confidence")
        normalized = parsed / 100.0
        return 0.0 if normalized == 0.0 else normalized


__all__ = ["TesseractTsvParser"]
