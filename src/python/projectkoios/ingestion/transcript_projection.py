from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.base import BaseCleanTranscriptProjector
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import Metadata, SourceSpan
from projectkoios.ingestion.transcription import StructuredTranscriptionResult

CLEAN_TRANSCRIPT_CONTRACT_VERSION = "1.0"
CLEAN_TRANSCRIPT_PROCESSOR_VERSION = "1"
_MAX_PAGES = 512
_MAX_BLOCKS = 32_768
_MAX_EXCLUSIONS = 16_384
_MAX_TEXT_CHARACTERS = 10_000_000
_MAX_BLOCK_CHARACTERS = 100_000
_CONTROL_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LINE_BREAK_HYPHENATION = re.compile(
    r"(?P<left>[A-Za-z]{2,})-\s*\n\s*(?P<right>[a-z][A-Za-z]*)"
)
_PAGE_NUMBER = re.compile(r"^(?:\d+|[ivxlcdm]+)$")
_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")


class CleanTranscriptLimitError(ValueError):
    """Raised before transcript projection exceeds a deterministic bound."""


class CleanTranscriptStatus(StrEnum):
    AUTOMATED_UNREVIEWED = "automated_unreviewed"


class CleanTranscriptExclusionReason(StrEnum):
    REPEATED_MARGIN = "repeated_margin"
    PAGE_NUMBER = "page_number"
    EMPTY_AFTER_SANITIZATION = "empty_after_sanitization"


@dataclass(frozen=True)
class CleanTranscriptConfiguration:
    top_margin_fraction: float = 0.12
    bottom_margin_fraction: float = 0.12
    minimum_repeated_margin_pages: int = 3
    repeated_margin_page_fraction: float = 0.20
    join_line_break_hyphenation: bool = True
    contract_version: str = CLEAN_TRANSCRIPT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_CONTRACT_VERSION:
            raise ValueError("unsupported clean-transcript configuration")
        for name, value in (
            ("top_margin_fraction", self.top_margin_fraction),
            ("bottom_margin_fraction", self.bottom_margin_fraction),
            (
                "repeated_margin_page_fraction",
                self.repeated_margin_page_fraction,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 0.5
            ):
                raise ValueError(f"{name} must be finite and in [0, 0.5]")
        if (
            isinstance(self.minimum_repeated_margin_pages, bool)
            or not isinstance(self.minimum_repeated_margin_pages, int)
            or self.minimum_repeated_margin_pages < 2
            or self.minimum_repeated_margin_pages > _MAX_PAGES
        ):
            raise ValueError(
                "minimum_repeated_margin_pages must be in [2, 512]"
            )
        if not isinstance(self.join_line_break_hyphenation, bool):
            raise TypeError("join_line_break_hyphenation must be boolean")

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "clean-transcript-configuration",
            self.top_margin_fraction,
            self.bottom_margin_fraction,
            self.minimum_repeated_margin_pages,
            self.repeated_margin_page_fraction,
            self.join_line_break_hyphenation,
        )


@dataclass(frozen=True)
class CleanTranscriptBlock:
    record_id: str
    block_id: str
    page_index: int
    printed_page_label: str | None
    order_index: int
    raw_text: str
    clean_text: str
    source_spans: tuple[SourceSpan, ...]
    transformations: Metadata
    contract_version: str = CLEAN_TRANSCRIPT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        block_id: str,
        page_index: int,
        printed_page_label: str | None,
        order_index: int,
        raw_text: str,
        clean_text: str,
        source_spans: tuple[SourceSpan, ...],
        transformations: Metadata,
    ) -> CleanTranscriptBlock:
        normalized = tuple(sorted(transformations))
        record_id = stable_id(
            "clean-transcript-block",
            block_id,
            page_index,
            printed_page_label,
            order_index,
            raw_text,
            clean_text,
            tuple(span.identity_parts() for span in source_spans),
            normalized,
        )
        return cls(
            record_id=record_id,
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            order_index=order_index,
            raw_text=raw_text,
            clean_text=clean_text,
            source_spans=source_spans,
            transformations=normalized,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_CONTRACT_VERSION:
            raise ValueError("unsupported clean-transcript block contract")
        if not self.block_id or not self.raw_text or not self.clean_text:
            raise ValueError("transcript block text and identity are required")
        if self.page_index < 0 or self.order_index < 0:
            raise ValueError("transcript block indices must be non-negative")
        if len(self.raw_text) > _MAX_BLOCK_CHARACTERS:
            raise CleanTranscriptLimitError("raw block text exceeds limit")
        if self.transformations != tuple(sorted(self.transformations)):
            raise ValueError("transcript transformations must be sorted")
        expected = stable_id(
            "clean-transcript-block",
            self.block_id,
            self.page_index,
            self.printed_page_label,
            self.order_index,
            self.raw_text,
            self.clean_text,
            tuple(span.identity_parts() for span in self.source_spans),
            self.transformations,
        )
        if self.record_id != expected:
            raise ValueError("clean-transcript block ID is inconsistent")


@dataclass(frozen=True)
class CleanTranscriptExclusion:
    exclusion_id: str
    block_id: str
    page_index: int
    printed_page_label: str | None
    reason: CleanTranscriptExclusionReason
    raw_text: str
    source_spans: tuple[SourceSpan, ...]
    contract_version: str = CLEAN_TRANSCRIPT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        block_id: str,
        page_index: int,
        printed_page_label: str | None,
        reason: CleanTranscriptExclusionReason,
        raw_text: str,
        source_spans: tuple[SourceSpan, ...],
    ) -> CleanTranscriptExclusion:
        exclusion_id = stable_id(
            "clean-transcript-exclusion",
            block_id,
            page_index,
            printed_page_label,
            reason,
            raw_text,
            tuple(span.identity_parts() for span in source_spans),
        )
        return cls(
            exclusion_id=exclusion_id,
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            reason=reason,
            raw_text=raw_text,
            source_spans=source_spans,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_CONTRACT_VERSION:
            raise ValueError("unsupported clean-transcript exclusion contract")
        if not self.block_id or not self.raw_text or self.page_index < 0:
            raise ValueError("transcript exclusion evidence is incomplete")
        if not isinstance(self.reason, CleanTranscriptExclusionReason):
            raise TypeError("transcript exclusion reason is unsupported")
        expected = stable_id(
            "clean-transcript-exclusion",
            self.block_id,
            self.page_index,
            self.printed_page_label,
            self.reason,
            self.raw_text,
            tuple(span.identity_parts() for span in self.source_spans),
        )
        if self.exclusion_id != expected:
            raise ValueError("clean-transcript exclusion ID is inconsistent")


@dataclass(frozen=True)
class CleanTranscriptPage:
    page_id: str
    page_index: int
    printed_page_label: str | None
    block_record_ids: tuple[str, ...]
    text: str
    text_sha256: str
    contract_version: str = CLEAN_TRANSCRIPT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        page_index: int,
        printed_page_label: str | None,
        block_record_ids: tuple[str, ...],
        text: str,
    ) -> CleanTranscriptPage:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        page_id = stable_id(
            "clean-transcript-page",
            page_index,
            printed_page_label,
            block_record_ids,
            digest,
        )
        return cls(
            page_id=page_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            block_record_ids=block_record_ids,
            text=text,
            text_sha256=digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_CONTRACT_VERSION:
            raise ValueError("unsupported clean-transcript page contract")
        if self.page_index < 0:
            raise ValueError("transcript page index must be non-negative")
        if (
            self.text_sha256
            != hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        ):
            raise ValueError("transcript page text hash is inconsistent")
        expected = stable_id(
            "clean-transcript-page",
            self.page_index,
            self.printed_page_label,
            self.block_record_ids,
            self.text_sha256,
        )
        if self.page_id != expected:
            raise ValueError("clean-transcript page ID is inconsistent")


@dataclass(frozen=True)
class CleanTranscriptArtifact:
    artifact_id: str
    transcription_result_id: str
    document_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    layout_result_ids: tuple[str, ...]
    pages: tuple[CleanTranscriptPage, ...]
    blocks: tuple[CleanTranscriptBlock, ...]
    exclusions: tuple[CleanTranscriptExclusion, ...]
    text: str
    text_sha256: str
    utf8_byte_length: int
    status: CleanTranscriptStatus
    warnings: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = CLEAN_TRANSCRIPT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        transcription_result: StructuredTranscriptionResult,
        layouts: tuple[PageLayoutResult, ...],
        pages: tuple[CleanTranscriptPage, ...],
        blocks: tuple[CleanTranscriptBlock, ...],
        exclusions: tuple[CleanTranscriptExclusion, ...],
        text: str,
        warnings: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> CleanTranscriptArtifact:
        document = transcription_result.transcription_input.document
        encoded = text.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        layout_ids = tuple(layout.result_id for layout in layouts)
        status = CleanTranscriptStatus.AUTOMATED_UNREVIEWED
        artifact_id = stable_id(
            "clean-transcript-artifact",
            transcription_result.result_id,
            document.document_id,
            document.source.source_id,
            document.source.blob_id,
            document.source.content_hash,
            layout_ids,
            tuple(page.page_id for page in pages),
            tuple(block.record_id for block in blocks),
            tuple(item.exclusion_id for item in exclusions),
            digest,
            len(encoded),
            status,
            warnings,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            artifact_id=artifact_id,
            transcription_result_id=transcription_result.result_id,
            document_id=document.document_id,
            source_id=document.source.source_id,
            source_blob_id=document.source.blob_id,
            source_content_hash=document.source.content_hash,
            layout_result_ids=layout_ids,
            pages=pages,
            blocks=blocks,
            exclusions=exclusions,
            text=text,
            text_sha256=digest,
            utf8_byte_length=len(encoded),
            status=status,
            warnings=warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_CONTRACT_VERSION:
            raise ValueError("unsupported clean-transcript artifact contract")
        if not all(
            (
                self.transcription_result_id,
                self.document_id,
                self.source_id,
                self.source_blob_id,
                self.source_content_hash,
                self.processor_name,
                self.processor_version,
                self.configuration_digest,
            )
        ):
            raise ValueError("clean-transcript artifact identity is incomplete")
        if len(self.pages) > _MAX_PAGES or len(self.blocks) > _MAX_BLOCKS:
            raise CleanTranscriptLimitError(
                "clean-transcript objects exceed limit"
            )
        if len(self.exclusions) > _MAX_EXCLUSIONS:
            raise CleanTranscriptLimitError(
                "transcript exclusions exceed limit"
            )
        if len(self.text) > _MAX_TEXT_CHARACTERS:
            raise CleanTranscriptLimitError(
                "clean transcript text exceeds limit"
            )
        encoded = self.text.encode("utf-8")
        if (
            self.utf8_byte_length != len(encoded)
            or self.text_sha256 != hashlib.sha256(encoded).hexdigest()
        ):
            raise ValueError("clean-transcript text identity is inconsistent")
        expected = stable_id(
            "clean-transcript-artifact",
            self.transcription_result_id,
            self.document_id,
            self.source_id,
            self.source_blob_id,
            self.source_content_hash,
            self.layout_result_ids,
            tuple(page.page_id for page in self.pages),
            tuple(block.record_id for block in self.blocks),
            tuple(item.exclusion_id for item in self.exclusions),
            self.text_sha256,
            self.utf8_byte_length,
            self.status,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.artifact_id != expected:
            raise ValueError("clean-transcript artifact ID is inconsistent")


class DeterministicCleanTranscriptProjector(BaseCleanTranscriptProjector):
    """Produce readable, source-linked text without claiming proofreading."""

    name = "deterministic-clean-transcript-projector"
    version = CLEAN_TRANSCRIPT_PROCESSOR_VERSION

    def __init__(
        self, configuration: CleanTranscriptConfiguration | None = None
    ) -> None:
        self.configuration = configuration or CleanTranscriptConfiguration()

    def project(
        self,
        transcription_result: StructuredTranscriptionResult,
        layouts: tuple[PageLayoutResult, ...],
    ) -> CleanTranscriptArtifact:
        if not isinstance(transcription_result, StructuredTranscriptionResult):
            raise TypeError(
                "transcription_result must be StructuredTranscriptionResult"
            )
        if not isinstance(layouts, tuple):
            raise TypeError("layouts must be a tuple")
        document = transcription_result.transcription_input.document
        if len(document.pages) > _MAX_PAGES:
            raise CleanTranscriptLimitError("document pages exceed limit")
        if len(layouts) != len(document.pages):
            raise ValueError("one layout is required per document page")
        layout_by_page = {layout.page_index: layout for layout in layouts}
        if len(layout_by_page) != len(layouts):
            raise ValueError("layout page indices must be unique")
        for page in document.pages:
            layout = layout_by_page.get(page.page_index)
            if layout is None or (
                layout.source_id != document.source.source_id
                or layout.source_blob_id != document.source.blob_id
                or layout.source_content_hash != document.source.content_hash
                or layout.raw_block_ids
                != tuple(block.block_id for block in page.blocks)
            ):
                raise ValueError("layout does not match transcript document")
        repeated_margin_keys = _repeated_margin_keys(
            transcription_result, layouts, self.configuration
        )
        records: list[CleanTranscriptBlock] = []
        exclusions: list[CleanTranscriptExclusion] = []
        pages: list[CleanTranscriptPage] = []
        warnings = {
            "automated_unreviewed_transcript",
            "layout_reading_order_is_proposed",
            "native_equation_text_is_not_proofread",
        }
        global_order = 0
        for page in document.pages:
            layout = layout_by_page[page.page_index]
            block_by_id = {block.block_id: block for block in page.blocks}
            text_ids = tuple(
                block.block_id
                for block in page.blocks
                if block.kind == "text" and block.text is not None
            )
            ordered_ids = tuple(
                block_id
                for block_id in layout.proposed_order
                if block_id in block_by_id
                and block_by_id[block_id].kind == "text"
                and block_by_id[block_id].text is not None
            )
            fallback_ids = tuple(
                block_id for block_id in text_ids if block_id not in ordered_ids
            )
            if fallback_ids:
                warnings.add("raw_block_order_fallback_retained")
            page_records: list[CleanTranscriptBlock] = []
            for block_id in (*ordered_ids, *fallback_ids):
                block = block_by_id[block_id]
                assert block.text is not None
                reason = _exclusion_reason(
                    block.text,
                    block.source_spans,
                    page.height,
                    repeated_margin_keys,
                    self.configuration,
                )
                if reason is not None:
                    exclusions.append(
                        CleanTranscriptExclusion.create(
                            block_id=block.block_id,
                            page_index=page.page_index,
                            printed_page_label=page.printed_page_label,
                            reason=reason,
                            raw_text=block.text,
                            source_spans=block.source_spans,
                        )
                    )
                    continue
                clean_text, transformations = _clean_text(
                    block.text, self.configuration
                )
                if not clean_text:
                    exclusions.append(
                        CleanTranscriptExclusion.create(
                            block_id=block.block_id,
                            page_index=page.page_index,
                            printed_page_label=page.printed_page_label,
                            reason=(
                                CleanTranscriptExclusionReason.EMPTY_AFTER_SANITIZATION
                            ),
                            raw_text=block.text,
                            source_spans=block.source_spans,
                        )
                    )
                    continue
                record = CleanTranscriptBlock.create(
                    block_id=block.block_id,
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                    order_index=global_order,
                    raw_text=block.text,
                    clean_text=clean_text,
                    source_spans=block.source_spans,
                    transformations=transformations,
                )
                records.append(record)
                page_records.append(record)
                global_order += 1
                if len(records) > _MAX_BLOCKS:
                    raise CleanTranscriptLimitError(
                        "clean-transcript blocks exceed limit"
                    )
            label = (
                "none"
                if page.printed_page_label is None
                else page.printed_page_label.replace('"', "'")
            )
            marker = (
                f'[[PAGE physical={page.page_index + 1} printed="{label}"]]'
            )
            body = "\n\n".join(item.clean_text for item in page_records)
            page_text = marker if not body else f"{marker}\n\n{body}"
            pages.append(
                CleanTranscriptPage.create(
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                    block_record_ids=tuple(
                        item.record_id for item in page_records
                    ),
                    text=page_text,
                )
            )
        if len(exclusions) > _MAX_EXCLUSIONS:
            raise CleanTranscriptLimitError(
                "transcript exclusions exceed limit"
            )
        text = "\n\n".join(page.text for page in pages) + "\n"
        return CleanTranscriptArtifact.create(
            transcription_result=transcription_result,
            layouts=layouts,
            pages=tuple(pages),
            blocks=tuple(records),
            exclusions=tuple(exclusions),
            text=text,
            warnings=tuple(sorted(warnings)),
            processor_name=self.name,
            processor_version=self.version,
            configuration_digest=self.configuration.configuration_digest,
        )


def _clean_text(
    text: str, configuration: CleanTranscriptConfiguration
) -> tuple[str, Metadata]:
    control_count = len(_CONTROL_CHARACTER.findall(text))
    soft_hyphen_count = text.count("\u00ad")
    value = _CONTROL_CHARACTER.sub(" ", text).replace("\u00ad", "")
    joined = 0
    if configuration.join_line_break_hyphenation:
        value, joined = _LINE_BREAK_HYPHENATION.subn(
            lambda match: match.group("left") + match.group("right"), value
        )
    normalized = _WHITESPACE.sub(" ", value).strip()
    transformations: Metadata = tuple(
        sorted(
            (
                ("control_characters_replaced", str(control_count)),
                ("line_break_hyphenations_joined", str(joined)),
                ("soft_hyphens_removed", str(soft_hyphen_count)),
                (
                    "unicode_normalization",
                    "none",
                ),
                ("whitespace_normalization", "collapse_unicode_whitespace"),
            )
        )
    )
    return normalized, transformations


def _repeated_margin_keys(
    transcription_result: StructuredTranscriptionResult,
    layouts: tuple[PageLayoutResult, ...],
    configuration: CleanTranscriptConfiguration,
) -> frozenset[str]:
    document = transcription_result.transcription_input.document
    layout_by_page = {layout.page_index: layout for layout in layouts}
    pages_by_key: dict[str, set[int]] = defaultdict(set)
    for page in document.pages:
        layout = layout_by_page[page.page_index]
        block_by_id = {block.block_id: block for block in page.blocks}
        for block_id in layout.raw_block_ids:
            block = block_by_id[block_id]
            if block.kind != "text" or block.text is None:
                continue
            if not _is_margin(block.source_spans, page.height, configuration):
                continue
            clean, _ = _clean_text(block.text, configuration)
            if clean:
                pages_by_key[_margin_key(clean)].add(page.page_index)
    threshold = max(
        configuration.minimum_repeated_margin_pages,
        math.ceil(
            len(document.pages) * configuration.repeated_margin_page_fraction
        ),
    )
    return frozenset(
        key
        for key, page_indices in pages_by_key.items()
        if len(page_indices) >= threshold
    )


def _exclusion_reason(
    text: str,
    spans: tuple[SourceSpan, ...],
    page_height: float,
    repeated_margin_keys: frozenset[str],
    configuration: CleanTranscriptConfiguration,
) -> CleanTranscriptExclusionReason | None:
    if not _is_margin(spans, page_height, configuration):
        return None
    clean, _ = _clean_text(text, configuration)
    if _PAGE_NUMBER.fullmatch(clean):
        return CleanTranscriptExclusionReason.PAGE_NUMBER
    if _margin_key(clean) in repeated_margin_keys:
        return CleanTranscriptExclusionReason.REPEATED_MARGIN
    return None


def _is_margin(
    spans: tuple[SourceSpan, ...],
    page_height: float,
    configuration: CleanTranscriptConfiguration,
) -> bool:
    boxes = tuple(
        span.bounding_box for span in spans if span.bounding_box is not None
    )
    if not boxes:
        return False
    y0 = min(box[1] for box in boxes)
    y1 = max(box[3] for box in boxes)
    return (
        y1 <= page_height * configuration.top_margin_fraction
        or y0 >= page_height * (1.0 - configuration.bottom_margin_fraction)
    )


def _margin_key(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).casefold()
    return _DIGITS.sub("#", normalized)
