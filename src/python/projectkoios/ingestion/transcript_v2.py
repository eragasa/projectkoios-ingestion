from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, fields
from enum import StrEnum

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import BoundingBox, Metadata, SourceSpan
from projectkoios.ingestion.structure import StructureKind
from projectkoios.ingestion.transcription import (
    StructuredTranscriptionResult,
    TranscriptionItemKind,
)

CLEAN_TRANSCRIPT_V2_CONTRACT_ID = "projectkoios.ingestion.clean-transcript"
CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION = "0.1.0"
CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION = 2
CLEAN_TRANSCRIPT_V2_CONFIGURATION_VERSION = "2"
CLEAN_TRANSCRIPT_V2_PROCESSOR_VERSION = "2"
_MAX_PAGES = 512
_MAX_BLOCKS = 32_768
_MAX_EXCLUSIONS = 16_384
_MAX_DECISIONS = 65_536
_MAX_FINDINGS = 65_536
_MAX_WARNINGS = 65_536
_MAX_TEXT_CHARACTERS = 10_000_000
_MAX_BLOCK_CHARACTERS = 100_000
_CONTROL_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LINE_BREAK_HYPHENATION = re.compile(
    r"(?P<left>[A-Za-z]{2,})-(?P<break>\s*\n\s*)"
    r"(?P<right>[a-z][A-Za-z]*)"
)
_PAGE_NUMBER = re.compile(r"^(?:\d+|[ivxlcdm]+)$")
_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")
_WORD_CHARACTER = re.compile(r"[A-Za-z]")


class CleanTranscriptV2LimitError(ValueError):
    """Raised before a transcript-v2 projection exceeds a hard bound."""


class CleanTranscriptV2Status(StrEnum):
    AUTOMATED_UNREVIEWED = "automated_unreviewed"


class DehyphenationOutcome(StrEnum):
    JOIN = "join"
    PRESERVE_HYPHEN = "preserve_hyphen"
    PRESERVE_BREAK_CONSERVATIVELY = "preserve_break_conservatively"
    NOT_APPLICABLE = "not_applicable"


class PageNumberOutcome(StrEnum):
    PAGE_NUMBER = "page_number"
    NOT_PAGE_NUMBER = "not_page_number"
    UNRESOLVED = "unresolved"


class PageNumberMethod(StrEnum):
    PRINTED_PAGE_LABEL = "printed_page_label"
    RECURRING_GEOMETRY_SEQUENCE = "recurring_geometry_sequence"
    TYPED_CONTENT = "typed_content"
    OUTSIDE_MARGIN = "outside_margin"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class PublisherFrontMatterKind(StrEnum):
    COVER = "cover"
    NOTICE = "notice"
    MASTHEAD = "masthead"
    LICENSING = "licensing"
    CITATION = "citation"
    UNRECOGNIZED = "unrecognized"


class ClassificationDisposition(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


class CleanTranscriptV2ExclusionReason(StrEnum):
    REPEATED_MARGIN = "repeated_margin"
    PAGE_NUMBER = "page_number"
    PUBLISHER_FRONT_MATTER = "publisher_front_matter"
    EMPTY_AFTER_SANITIZATION = "empty_after_sanitization"


@dataclass(frozen=True)
class CleanTranscriptV2Configuration:
    top_margin_fraction: float = 0.12
    bottom_margin_fraction: float = 0.12
    minimum_repeated_margin_pages: int = 3
    repeated_margin_page_fraction: float = 0.20
    minimum_page_sequence_length: int = 3
    page_number_horizontal_tolerance_fraction: float = 0.04
    accepted_joined_forms: tuple[str, ...] = ()
    accepted_hyphenated_forms: tuple[str, ...] = ()
    excluded_publisher_front_matter: tuple[PublisherFrontMatterKind, ...] = ()
    configuration_version: str = CLEAN_TRANSCRIPT_V2_CONFIGURATION_VERSION

    def __post_init__(self) -> None:
        if (
            self.configuration_version
            != CLEAN_TRANSCRIPT_V2_CONFIGURATION_VERSION
        ):
            raise ValueError("unsupported transcript-v2 configuration version")
        for name in (
            "top_margin_fraction",
            "bottom_margin_fraction",
            "repeated_margin_page_fraction",
            "page_number_horizontal_tolerance_fraction",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 0.5
            ):
                raise ValueError(f"{name} must be finite and in [0, 0.5]")
        for name, minimum in (
            ("minimum_repeated_margin_pages", 2),
            ("minimum_page_sequence_length", 2),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= _MAX_PAGES
            ):
                raise ValueError(f"{name} must be in [{minimum}, {_MAX_PAGES}]")
        joined = _normalized_forms(
            "accepted_joined_forms", self.accepted_joined_forms, hyphen=False
        )
        hyphenated = _normalized_forms(
            "accepted_hyphenated_forms",
            self.accepted_hyphenated_forms,
            hyphen=True,
        )
        if set(joined) & {item.replace("-", "") for item in hyphenated}:
            raise ValueError("lexical evidence sets must not conflict")
        object.__setattr__(self, "accepted_joined_forms", joined)
        object.__setattr__(self, "accepted_hyphenated_forms", hyphenated)
        excluded = self.excluded_publisher_front_matter
        if not isinstance(excluded, tuple) or any(
            not isinstance(item, PublisherFrontMatterKind) for item in excluded
        ):
            raise TypeError("publisher-front-matter policy is invalid")
        if len(set(excluded)) != len(excluded):
            raise ValueError(
                "publisher-front-matter policy contains duplicates"
            )
        object.__setattr__(
            self,
            "excluded_publisher_front_matter",
            tuple(sorted(excluded, key=lambda item: item.value)),
        )

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "clean-transcript-v2-configuration", self.identity_parts()
        )

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (field.name, getattr(self, field.name)) for field in fields(self)
        )


@dataclass(frozen=True)
class DehyphenationDecision:
    decision_id: str
    block_id: str
    page_index: int
    printed_page_label: str | None
    raw_fragment: str
    start_offset: int
    end_offset: int
    left_fragment: str
    right_fragment: str
    candidate_joined: str
    candidate_hyphenated: str
    outcome: DehyphenationOutcome
    rule_id: str
    evidence: Metadata
    source_spans: tuple[SourceSpan, ...]
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        block_id: str,
        page_index: int,
        printed_page_label: str | None,
        raw_fragment: str,
        start_offset: int,
        end_offset: int,
        left_fragment: str,
        right_fragment: str,
        outcome: DehyphenationOutcome,
        evidence: Metadata,
        source_spans: tuple[SourceSpan, ...],
    ) -> DehyphenationDecision:
        candidate_joined = left_fragment + right_fragment
        candidate_hyphenated = f"{left_fragment}-{right_fragment}"
        normalized_evidence = tuple(sorted(evidence))
        rule_id = "document-lexical-evidence-v1"
        decision_id = stable_id(
            "clean-transcript-v2-dehyphenation",
            block_id,
            page_index,
            printed_page_label,
            raw_fragment,
            start_offset,
            end_offset,
            left_fragment,
            right_fragment,
            candidate_joined,
            candidate_hyphenated,
            outcome,
            rule_id,
            normalized_evidence,
            _span_parts(source_spans),
        )
        return cls(
            decision_id=decision_id,
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            raw_fragment=raw_fragment,
            start_offset=start_offset,
            end_offset=end_offset,
            left_fragment=left_fragment,
            right_fragment=right_fragment,
            candidate_joined=candidate_joined,
            candidate_hyphenated=candidate_hyphenated,
            outcome=outcome,
            rule_id=rule_id,
            evidence=normalized_evidence,
            source_spans=source_spans,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION:
            raise ValueError("unsupported dehyphenation decision version")
        if not isinstance(self.outcome, DehyphenationOutcome):
            raise TypeError("unsupported dehyphenation outcome")
        if (
            not self.block_id
            or not self.raw_fragment
            or not self.left_fragment
            or not self.right_fragment
            or self.page_index < 0
            or self.start_offset < 0
            or self.end_offset <= self.start_offset
        ):
            raise ValueError("dehyphenation decision evidence is incomplete")
        if self.candidate_joined != self.left_fragment + self.right_fragment:
            raise ValueError("joined dehyphenation candidate is inconsistent")
        if self.candidate_hyphenated != (
            f"{self.left_fragment}-{self.right_fragment}"
        ):
            raise ValueError(
                "hyphenated dehyphenation candidate is inconsistent"
            )
        expected = stable_id(
            "clean-transcript-v2-dehyphenation",
            self.block_id,
            self.page_index,
            self.printed_page_label,
            self.raw_fragment,
            self.start_offset,
            self.end_offset,
            self.left_fragment,
            self.right_fragment,
            self.candidate_joined,
            self.candidate_hyphenated,
            self.outcome,
            self.rule_id,
            self.evidence,
            _span_parts(self.source_spans),
        )
        if self.decision_id != expected:
            raise ValueError("dehyphenation decision ID is inconsistent")


@dataclass(frozen=True)
class PageNumberClassification:
    classification_id: str
    block_id: str
    page_index: int
    printed_page_label: str | None
    raw_text: str
    normalized_value: str
    bounding_box: BoundingBox | None
    outcome: PageNumberOutcome
    method: PageNumberMethod
    rule_version: str
    evidence: Metadata
    source_spans: tuple[SourceSpan, ...]
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        block_id: str,
        page_index: int,
        printed_page_label: str | None,
        raw_text: str,
        normalized_value: str,
        bounding_box: BoundingBox | None,
        outcome: PageNumberOutcome,
        method: PageNumberMethod,
        evidence: Metadata,
        source_spans: tuple[SourceSpan, ...],
    ) -> PageNumberClassification:
        normalized_evidence = tuple(sorted(evidence))
        rule_version = "page-number-evidence-v1"
        classification_id = stable_id(
            "clean-transcript-v2-page-number",
            block_id,
            page_index,
            printed_page_label,
            raw_text,
            normalized_value,
            bounding_box,
            outcome,
            method,
            rule_version,
            normalized_evidence,
            _span_parts(source_spans),
        )
        return cls(
            classification_id=classification_id,
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            raw_text=raw_text,
            normalized_value=normalized_value,
            bounding_box=bounding_box,
            outcome=outcome,
            method=method,
            rule_version=rule_version,
            evidence=normalized_evidence,
            source_spans=source_spans,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION:
            raise ValueError("unsupported page-number classification version")
        if not isinstance(self.outcome, PageNumberOutcome) or not isinstance(
            self.method, PageNumberMethod
        ):
            raise TypeError("unsupported page-number classification")
        if (
            not self.block_id
            or not self.raw_text
            or not self.normalized_value
            or self.page_index < 0
        ):
            raise ValueError(
                "page-number classification evidence is incomplete"
            )
        if not _PAGE_NUMBER.fullmatch(self.normalized_value):
            raise ValueError("page-number classification value is not numeric")
        expected = stable_id(
            "clean-transcript-v2-page-number",
            self.block_id,
            self.page_index,
            self.printed_page_label,
            self.raw_text,
            self.normalized_value,
            self.bounding_box,
            self.outcome,
            self.method,
            self.rule_version,
            self.evidence,
            _span_parts(self.source_spans),
        )
        if self.classification_id != expected:
            raise ValueError("page-number classification ID is inconsistent")


@dataclass(frozen=True)
class PublisherFrontMatterClassification:
    classification_id: str
    block_id: str
    page_index: int
    kind: PublisherFrontMatterKind
    disposition: ClassificationDisposition
    method: str
    evidence: Metadata
    source_spans: tuple[SourceSpan, ...]
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        block_id: str,
        page_index: int,
        kind: PublisherFrontMatterKind,
        disposition: ClassificationDisposition,
        evidence: Metadata,
        source_spans: tuple[SourceSpan, ...],
    ) -> PublisherFrontMatterClassification:
        method = "explicit-publisher-lexicon-v1"
        normalized_evidence = tuple(sorted(evidence))
        classification_id = stable_id(
            "clean-transcript-v2-publisher-front-matter",
            block_id,
            page_index,
            kind,
            disposition,
            method,
            normalized_evidence,
            _span_parts(source_spans),
        )
        return cls(
            classification_id=classification_id,
            block_id=block_id,
            page_index=page_index,
            kind=kind,
            disposition=disposition,
            method=method,
            evidence=normalized_evidence,
            source_spans=source_spans,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION:
            raise ValueError("unsupported publisher classification version")
        if not isinstance(
            self.kind, PublisherFrontMatterKind
        ) or not isinstance(self.disposition, ClassificationDisposition):
            raise TypeError("unsupported publisher-front-matter classification")
        if not self.block_id or self.page_index < 0 or not self.method:
            raise ValueError("publisher classification evidence is incomplete")
        expected = stable_id(
            "clean-transcript-v2-publisher-front-matter",
            self.block_id,
            self.page_index,
            self.kind,
            self.disposition,
            self.method,
            self.evidence,
            _span_parts(self.source_spans),
        )
        if self.classification_id != expected:
            raise ValueError("publisher classification ID is inconsistent")


@dataclass(frozen=True)
class PrivateUseGlyphFinding:
    finding_id: str
    block_id: str
    page_index: int
    printed_page_label: str | None
    character_offset: int
    code_point: str
    raw_character: str
    source_spans: tuple[SourceSpan, ...]
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        block_id: str,
        page_index: int,
        printed_page_label: str | None,
        character_offset: int,
        raw_character: str,
        source_spans: tuple[SourceSpan, ...],
    ) -> PrivateUseGlyphFinding:
        code_point = f"U+{ord(raw_character):04X}"
        finding_id = stable_id(
            "clean-transcript-v2-private-use-glyph",
            block_id,
            page_index,
            printed_page_label,
            character_offset,
            code_point,
            raw_character,
            _span_parts(source_spans),
        )
        return cls(
            finding_id=finding_id,
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            character_offset=character_offset,
            code_point=code_point,
            raw_character=raw_character,
            source_spans=source_spans,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION:
            raise ValueError("unsupported private-use finding version")
        if (
            not self.block_id
            or self.page_index < 0
            or self.character_offset < 0
            or len(self.raw_character) != 1
            or unicodedata.category(self.raw_character) != "Co"
            or self.code_point != f"U+{ord(self.raw_character):04X}"
        ):
            raise ValueError("private-use glyph evidence is inconsistent")
        expected = stable_id(
            "clean-transcript-v2-private-use-glyph",
            self.block_id,
            self.page_index,
            self.printed_page_label,
            self.character_offset,
            self.code_point,
            self.raw_character,
            _span_parts(self.source_spans),
        )
        if self.finding_id != expected:
            raise ValueError("private-use glyph finding ID is inconsistent")


@dataclass(frozen=True)
class CleanTranscriptV2Block:
    record_id: str
    block_id: str
    page_index: int
    printed_page_label: str | None
    order_index: int
    raw_text: str
    clean_text: str
    source_spans: tuple[SourceSpan, ...]
    transformations: Metadata
    dehyphenation_decision_ids: tuple[str, ...]
    page_number_classification_id: str | None
    publisher_classification_id: str | None
    private_use_finding_ids: tuple[str, ...]
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

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
        dehyphenation_decision_ids: tuple[str, ...],
        page_number_classification_id: str | None,
        publisher_classification_id: str | None,
        private_use_finding_ids: tuple[str, ...],
    ) -> CleanTranscriptV2Block:
        normalized = tuple(sorted(transformations))
        parts = (
            block_id,
            page_index,
            printed_page_label,
            order_index,
            raw_text,
            clean_text,
            _span_parts(source_spans),
            normalized,
            dehyphenation_decision_ids,
            page_number_classification_id,
            publisher_classification_id,
            private_use_finding_ids,
        )
        return cls(
            record_id=stable_id("clean-transcript-v2-block", *parts),
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            order_index=order_index,
            raw_text=raw_text,
            clean_text=clean_text,
            source_spans=source_spans,
            transformations=normalized,
            dehyphenation_decision_ids=dehyphenation_decision_ids,
            page_number_classification_id=page_number_classification_id,
            publisher_classification_id=publisher_classification_id,
            private_use_finding_ids=private_use_finding_ids,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION:
            raise ValueError("unsupported transcript-v2 block version")
        if (
            not self.block_id
            or not self.raw_text
            or not self.clean_text
            or self.page_index < 0
            or self.order_index < 0
        ):
            raise ValueError("transcript-v2 block evidence is incomplete")
        if len(self.raw_text) > _MAX_BLOCK_CHARACTERS:
            raise CleanTranscriptV2LimitError("raw block text exceeds limit")
        expected = stable_id(
            "clean-transcript-v2-block",
            self.block_id,
            self.page_index,
            self.printed_page_label,
            self.order_index,
            self.raw_text,
            self.clean_text,
            _span_parts(self.source_spans),
            self.transformations,
            self.dehyphenation_decision_ids,
            self.page_number_classification_id,
            self.publisher_classification_id,
            self.private_use_finding_ids,
        )
        if self.record_id != expected:
            raise ValueError("transcript-v2 block ID is inconsistent")


@dataclass(frozen=True)
class CleanTranscriptV2Exclusion:
    exclusion_id: str
    block_id: str
    page_index: int
    printed_page_label: str | None
    reason: CleanTranscriptV2ExclusionReason
    raw_text: str
    source_spans: tuple[SourceSpan, ...]
    decision_id: str | None = None
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        block_id: str,
        page_index: int,
        printed_page_label: str | None,
        reason: CleanTranscriptV2ExclusionReason,
        raw_text: str,
        source_spans: tuple[SourceSpan, ...],
        decision_id: str | None = None,
    ) -> CleanTranscriptV2Exclusion:
        parts = (
            block_id,
            page_index,
            printed_page_label,
            reason,
            raw_text,
            _span_parts(source_spans),
            decision_id,
        )
        return cls(
            exclusion_id=stable_id("clean-transcript-v2-exclusion", *parts),
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            reason=reason,
            raw_text=raw_text,
            source_spans=source_spans,
            decision_id=decision_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION:
            raise ValueError("unsupported transcript-v2 exclusion version")
        if (
            not self.block_id
            or not self.raw_text
            or self.page_index < 0
            or not isinstance(self.reason, CleanTranscriptV2ExclusionReason)
        ):
            raise ValueError("transcript-v2 exclusion evidence is incomplete")
        if (
            self.reason
            in {
                CleanTranscriptV2ExclusionReason.PAGE_NUMBER,
                CleanTranscriptV2ExclusionReason.PUBLISHER_FRONT_MATTER,
            }
            and not self.decision_id
        ):
            raise ValueError("typed exclusion requires its decision identity")
        expected = stable_id(
            "clean-transcript-v2-exclusion",
            self.block_id,
            self.page_index,
            self.printed_page_label,
            self.reason,
            self.raw_text,
            _span_parts(self.source_spans),
            self.decision_id,
        )
        if self.exclusion_id != expected:
            raise ValueError("transcript-v2 exclusion ID is inconsistent")


@dataclass(frozen=True)
class CleanTranscriptV2Page:
    page_id: str
    page_index: int
    printed_page_label: str | None
    block_record_ids: tuple[str, ...]
    text: str
    text_sha256: str
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        page_index: int,
        printed_page_label: str | None,
        block_record_ids: tuple[str, ...],
        text: str,
    ) -> CleanTranscriptV2Page:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        page_id = stable_id(
            "clean-transcript-v2-page",
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
        if self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION:
            raise ValueError("unsupported transcript-v2 page version")
        digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if self.page_index < 0 or self.text_sha256 != digest:
            raise ValueError("transcript-v2 page evidence is inconsistent")
        expected = stable_id(
            "clean-transcript-v2-page",
            self.page_index,
            self.printed_page_label,
            self.block_record_ids,
            self.text_sha256,
        )
        if self.page_id != expected:
            raise ValueError("transcript-v2 page ID is inconsistent")


@dataclass(frozen=True)
class CleanTranscriptV2Artifact:
    artifact_id: str
    contract_id: str
    artifact_generation: int
    transcription_result_id: str
    document_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    layout_result_ids: tuple[str, ...]
    pages: tuple[CleanTranscriptV2Page, ...]
    blocks: tuple[CleanTranscriptV2Block, ...]
    exclusions: tuple[CleanTranscriptV2Exclusion, ...]
    dehyphenation_decisions: tuple[DehyphenationDecision, ...]
    page_number_classifications: tuple[PageNumberClassification, ...]
    publisher_front_matter: tuple[PublisherFrontMatterClassification, ...]
    private_use_glyph_findings: tuple[PrivateUseGlyphFinding, ...]
    text: str
    text_sha256: str
    utf8_byte_length: int
    status: CleanTranscriptV2Status
    warnings: tuple[str, ...]
    processor_name: str
    processor_version: str
    configuration_digest: str
    contract_version: str = CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        transcription_result: StructuredTranscriptionResult,
        layouts: tuple[PageLayoutResult, ...],
        pages: tuple[CleanTranscriptV2Page, ...],
        blocks: tuple[CleanTranscriptV2Block, ...],
        exclusions: tuple[CleanTranscriptV2Exclusion, ...],
        dehyphenation_decisions: tuple[DehyphenationDecision, ...],
        page_number_classifications: tuple[PageNumberClassification, ...],
        publisher_front_matter: tuple[PublisherFrontMatterClassification, ...],
        private_use_glyph_findings: tuple[PrivateUseGlyphFinding, ...],
        text: str,
        warnings: tuple[str, ...],
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
    ) -> CleanTranscriptV2Artifact:
        document = transcription_result.transcription_input.document
        encoded = text.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        layout_ids = tuple(layout.result_id for layout in layouts)
        normalized_warnings = tuple(sorted(set(warnings)))
        status = CleanTranscriptV2Status.AUTOMATED_UNREVIEWED
        identity_parts = (
            CLEAN_TRANSCRIPT_V2_CONTRACT_ID,
            CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION,
            CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION,
            transcription_result.result_id,
            document.document_id,
            document.source.source_id,
            document.source.blob_id,
            document.source.content_hash,
            layout_ids,
            tuple(page.page_id for page in pages),
            tuple(block.record_id for block in blocks),
            tuple(item.exclusion_id for item in exclusions),
            tuple(item.decision_id for item in dehyphenation_decisions),
            tuple(
                item.classification_id for item in page_number_classifications
            ),
            tuple(item.classification_id for item in publisher_front_matter),
            tuple(item.finding_id for item in private_use_glyph_findings),
            digest,
            len(encoded),
            status,
            normalized_warnings,
            processor_name,
            processor_version,
            configuration_digest,
        )
        return cls(
            artifact_id=stable_id(
                "clean-transcript-v2-artifact", *identity_parts
            ),
            contract_id=CLEAN_TRANSCRIPT_V2_CONTRACT_ID,
            artifact_generation=CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION,
            transcription_result_id=transcription_result.result_id,
            document_id=document.document_id,
            source_id=document.source.source_id,
            source_blob_id=document.source.blob_id,
            source_content_hash=document.source.content_hash,
            layout_result_ids=layout_ids,
            pages=pages,
            blocks=blocks,
            exclusions=exclusions,
            dehyphenation_decisions=dehyphenation_decisions,
            page_number_classifications=page_number_classifications,
            publisher_front_matter=publisher_front_matter,
            private_use_glyph_findings=private_use_glyph_findings,
            text=text,
            text_sha256=digest,
            utf8_byte_length=len(encoded),
            status=status,
            warnings=normalized_warnings,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=configuration_digest,
        )

    def __post_init__(self) -> None:
        if (
            self.contract_id != CLEAN_TRANSCRIPT_V2_CONTRACT_ID
            or self.contract_version != CLEAN_TRANSCRIPT_V2_CONTRACT_VERSION
            or self.artifact_generation
            != CLEAN_TRANSCRIPT_V2_ARTIFACT_GENERATION
        ):
            raise ValueError("unsupported transcript-v2 artifact contract")
        for bounded_values, limit in (
            (self.pages, _MAX_PAGES),
            (self.blocks, _MAX_BLOCKS),
            (self.exclusions, _MAX_EXCLUSIONS),
            (self.dehyphenation_decisions, _MAX_DECISIONS),
            (self.page_number_classifications, _MAX_DECISIONS),
            (self.publisher_front_matter, _MAX_DECISIONS),
            (self.private_use_glyph_findings, _MAX_FINDINGS),
            (self.warnings, _MAX_WARNINGS),
        ):
            if len(bounded_values) > limit:
                raise CleanTranscriptV2LimitError(
                    "transcript-v2 objects exceed limit"
                )
        if len(self.text) > _MAX_TEXT_CHARACTERS:
            raise CleanTranscriptV2LimitError(
                "transcript-v2 text exceeds limit"
            )
        encoded = self.text.encode("utf-8")
        if (
            len(encoded) != self.utf8_byte_length
            or hashlib.sha256(encoded).hexdigest() != self.text_sha256
        ):
            raise ValueError("transcript-v2 text identity is inconsistent")
        if self.warnings != tuple(sorted(set(self.warnings))):
            raise ValueError("transcript-v2 warnings must be sorted and unique")
        expected_text = "\n\n".join(page.text for page in self.pages) + "\n"
        if self.text != expected_text:
            raise ValueError("transcript-v2 text differs from page projections")
        _require_unique(
            "block record IDs", tuple(item.record_id for item in self.blocks)
        )
        _require_unique(
            "exclusion IDs",
            tuple(item.exclusion_id for item in self.exclusions),
        )
        covered = (
            *(item.block_id for item in self.blocks),
            *(item.block_id for item in self.exclusions),
        )
        _require_unique("covered block IDs", covered)
        decision_by_id = {
            item.decision_id: item for item in self.dehyphenation_decisions
        }
        page_classification_by_id = {
            item.classification_id: item
            for item in self.page_number_classifications
        }
        publisher_by_id = {
            item.classification_id: item for item in self.publisher_front_matter
        }
        finding_by_id = {
            item.finding_id: item for item in self.private_use_glyph_findings
        }
        for name, identity_map, expected_count in (
            (
                "dehyphenation decision IDs",
                decision_by_id,
                len(self.dehyphenation_decisions),
            ),
            (
                "page-number classification IDs",
                page_classification_by_id,
                len(self.page_number_classifications),
            ),
            (
                "publisher classification IDs",
                publisher_by_id,
                len(self.publisher_front_matter),
            ),
            (
                "private-use finding IDs",
                finding_by_id,
                len(self.private_use_glyph_findings),
            ),
        ):
            if len(identity_map) != expected_count:
                raise ValueError(f"{name} must be unique")
        block_by_id = {item.block_id: item for item in self.blocks}
        raw_text_by_block = {
            **{item.block_id: item.raw_text for item in self.blocks},
            **{item.block_id: item.raw_text for item in self.exclusions},
        }
        expected_private_use = {
            (block_id, offset, character)
            for block_id, raw_text in raw_text_by_block.items()
            for offset, character in enumerate(raw_text)
            if unicodedata.category(character) == "Co"
        }
        actual_private_use = {
            (item.block_id, item.character_offset, item.raw_character)
            for item in self.private_use_glyph_findings
        }
        if actual_private_use != expected_private_use:
            raise ValueError(
                "private-use findings must exactly cover retained raw evidence"
            )
        for block in self.blocks:
            for decision_id in block.dehyphenation_decision_ids:
                decision = decision_by_id.get(decision_id)
                if decision is None or decision.block_id != block.block_id:
                    raise ValueError("block dehyphenation link is inconsistent")
                if (
                    block.raw_text[decision.start_offset : decision.end_offset]
                    != decision.raw_fragment
                ):
                    raise ValueError("dehyphenation source fragment is stale")
            if block.page_number_classification_id is not None:
                page_classification = page_classification_by_id.get(
                    block.page_number_classification_id
                )
                if (
                    page_classification is None
                    or page_classification.block_id != block.block_id
                ):
                    raise ValueError("block page-number link is inconsistent")
            if block.publisher_classification_id is not None:
                publisher_classification = publisher_by_id.get(
                    block.publisher_classification_id
                )
                if (
                    publisher_classification is None
                    or publisher_classification.block_id != block.block_id
                ):
                    raise ValueError("block publisher link is inconsistent")
            for finding_id in block.private_use_finding_ids:
                finding = finding_by_id.get(finding_id)
                if finding is None or finding.block_id != block.block_id:
                    raise ValueError("block private-use link is inconsistent")
                if (
                    finding.character_offset >= len(block.raw_text)
                    or block.raw_text[finding.character_offset]
                    != finding.raw_character
                ):
                    raise ValueError("private-use glyph source offset is stale")
        for decision in self.dehyphenation_decisions:
            if decision.block_id not in block_by_id:
                raise ValueError("dehyphenation decision is not retained")
        expected_id = stable_id(
            "clean-transcript-v2-artifact",
            self.contract_id,
            self.contract_version,
            self.artifact_generation,
            self.transcription_result_id,
            self.document_id,
            self.source_id,
            self.source_blob_id,
            self.source_content_hash,
            self.layout_result_ids,
            tuple(page.page_id for page in self.pages),
            tuple(block.record_id for block in self.blocks),
            tuple(item.exclusion_id for item in self.exclusions),
            tuple(item.decision_id for item in self.dehyphenation_decisions),
            tuple(
                item.classification_id
                for item in self.page_number_classifications
            ),
            tuple(
                item.classification_id for item in self.publisher_front_matter
            ),
            tuple(item.finding_id for item in self.private_use_glyph_findings),
            self.text_sha256,
            self.utf8_byte_length,
            self.status,
            self.warnings,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
        )
        if self.artifact_id != expected_id:
            raise ValueError("transcript-v2 artifact ID is inconsistent")


@dataclass(frozen=True)
class _NumericCandidate:
    block_id: str
    page_index: int
    printed_page_label: str | None
    raw_text: str
    normalized_value: str
    bounding_box: BoundingBox | None
    source_spans: tuple[SourceSpan, ...]
    page_width: float
    page_height: float


class DeterministicCleanTranscriptV2Projector:
    """Create an evidence-conservative transcript-v2 projection."""

    name = "deterministic-clean-transcript-projector"
    version = CLEAN_TRANSCRIPT_V2_PROCESSOR_VERSION

    def __init__(
        self, configuration: CleanTranscriptV2Configuration | None = None
    ) -> None:
        self.configuration = configuration or CleanTranscriptV2Configuration()

    def project(
        self,
        transcription_result: StructuredTranscriptionResult,
        layouts: tuple[PageLayoutResult, ...],
    ) -> CleanTranscriptV2Artifact:
        document, layout_by_page = _validate_inputs(
            transcription_result, layouts
        )
        configuration = self.configuration
        all_text = tuple(
            block.text
            for page in document.pages
            for block in page.blocks
            if block.kind == "text" and block.text is not None
        )
        protected_ids = {
            block_id
            for item in transcription_result.items
            if item.item_kind
            in {
                TranscriptionItemKind.EQUATION,
                TranscriptionItemKind.TABLE,
                TranscriptionItemKind.FIGURE,
            }
            for block_id in item.source_block_ids
        }
        numeric_candidates = _numeric_candidates(document)
        sequence_ids = _recurring_sequence_ids(
            numeric_candidates, configuration
        )
        printed_label_match_counts = Counter(
            (candidate.page_index, candidate.normalized_value)
            for candidate in numeric_candidates
            if candidate.printed_page_label is not None
            and _basic_clean(candidate.printed_page_label).casefold()
            == candidate.normalized_value
        )
        page_classifications = tuple(
            _classify_page_number(
                candidate,
                protected_ids=protected_ids,
                recurring_sequence_ids=sequence_ids,
                printed_label_match_count=printed_label_match_counts[
                    (candidate.page_index, candidate.normalized_value)
                ],
                configuration=configuration,
            )
            for candidate in numeric_candidates
        )
        page_classification_by_block = {
            item.block_id: item for item in page_classifications
        }
        publisher_classifications = _publisher_classifications(
            transcription_result, configuration
        )
        publisher_by_block = {
            item.block_id: item for item in publisher_classifications
        }
        repeated_margin_keys = _repeated_margin_keys(
            transcription_result, layouts, configuration
        )
        records: list[CleanTranscriptV2Block] = []
        exclusions: list[CleanTranscriptV2Exclusion] = []
        pages: list[CleanTranscriptV2Page] = []
        dehyphenation: list[DehyphenationDecision] = []
        glyph_findings: list[PrivateUseGlyphFinding] = []
        warnings = {
            "automated_unreviewed_transcript",
            "layout_reading_order_is_proposed",
            "native_equation_text_is_not_proofread",
        }
        global_order = 0
        for page in document.pages:
            layout = layout_by_page[page.page_index]
            block_by_id = {block.block_id: block for block in page.blocks}
            root_order = _text_block_order(page.blocks, layout.proposed_order)
            ordered_count = sum(
                1
                for block_id in layout.proposed_order
                if block_id in block_by_id
            )
            if ordered_count < len(root_order):
                warnings.add("raw_block_order_fallback_retained")
            page_records: list[CleanTranscriptV2Block] = []
            for block_id in root_order:
                block = block_by_id[block_id]
                assert block.text is not None
                page_classification = page_classification_by_block.get(block_id)
                publisher_classification = publisher_by_block.get(block_id)
                findings = _private_use_findings(
                    block_id=block_id,
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                    text=block.text,
                    source_spans=block.source_spans,
                )
                glyph_findings.extend(findings)
                if findings:
                    warnings.add("private_use_glyph_retained")
                if (
                    page_classification is not None
                    and page_classification.outcome
                    is PageNumberOutcome.PAGE_NUMBER
                ):
                    exclusions.append(
                        CleanTranscriptV2Exclusion.create(
                            block_id=block_id,
                            page_index=page.page_index,
                            printed_page_label=page.printed_page_label,
                            reason=CleanTranscriptV2ExclusionReason.PAGE_NUMBER,
                            raw_text=block.text,
                            source_spans=block.source_spans,
                            decision_id=page_classification.classification_id,
                        )
                    )
                    continue
                if (
                    publisher_classification is not None
                    and publisher_classification.disposition
                    is ClassificationDisposition.EXCLUDED
                ):
                    exclusions.append(
                        CleanTranscriptV2Exclusion.create(
                            block_id=block_id,
                            page_index=page.page_index,
                            printed_page_label=page.printed_page_label,
                            reason=(
                                CleanTranscriptV2ExclusionReason.PUBLISHER_FRONT_MATTER
                            ),
                            raw_text=block.text,
                            source_spans=block.source_spans,
                            decision_id=publisher_classification.classification_id,
                        )
                    )
                    continue
                clean_for_margin = _basic_clean(block.text)
                if (
                    _is_margin(
                        block.source_spans,
                        page.height,
                        configuration,
                    )
                    and _margin_key(clean_for_margin) in repeated_margin_keys
                ):
                    exclusions.append(
                        CleanTranscriptV2Exclusion.create(
                            block_id=block_id,
                            page_index=page.page_index,
                            printed_page_label=page.printed_page_label,
                            reason=(
                                CleanTranscriptV2ExclusionReason.REPEATED_MARGIN
                            ),
                            raw_text=block.text,
                            source_spans=block.source_spans,
                        )
                    )
                    continue
                clean_text, transformations, decisions = _clean_text(
                    block_id=block_id,
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                    text=block.text,
                    source_spans=block.source_spans,
                    all_text=all_text,
                    configuration=configuration,
                )
                dehyphenation.extend(decisions)
                if any(
                    decision.outcome
                    is DehyphenationOutcome.PRESERVE_BREAK_CONSERVATIVELY
                    for decision in decisions
                ):
                    warnings.add("ambiguous_dehyphenation_retained")
                if _metadata_count(
                    transformations, "control_character_offsets"
                ):
                    warnings.add("control_characters_replaced")
                if _metadata_count(transformations, "soft_hyphen_offsets"):
                    warnings.add("soft_hyphens_removed")
                if (
                    page_classification is not None
                    and page_classification.outcome
                    is PageNumberOutcome.UNRESOLVED
                ):
                    warnings.add("unresolved_page_number_classification")
                if (
                    publisher_classification is not None
                    and publisher_classification.kind
                    is PublisherFrontMatterKind.UNRECOGNIZED
                ):
                    warnings.add("unrecognized_publisher_front_matter")
                if not clean_text:
                    exclusions.append(
                        CleanTranscriptV2Exclusion.create(
                            block_id=block_id,
                            page_index=page.page_index,
                            printed_page_label=page.printed_page_label,
                            reason=(
                                CleanTranscriptV2ExclusionReason.EMPTY_AFTER_SANITIZATION
                            ),
                            raw_text=block.text,
                            source_spans=block.source_spans,
                        )
                    )
                    continue
                record = CleanTranscriptV2Block.create(
                    block_id=block_id,
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                    order_index=global_order,
                    raw_text=block.text,
                    clean_text=clean_text,
                    source_spans=block.source_spans,
                    transformations=transformations,
                    dehyphenation_decision_ids=tuple(
                        item.decision_id for item in decisions
                    ),
                    page_number_classification_id=(
                        page_classification.classification_id
                        if page_classification is not None
                        else None
                    ),
                    publisher_classification_id=(
                        publisher_classification.classification_id
                        if publisher_classification is not None
                        else None
                    ),
                    private_use_finding_ids=tuple(
                        item.finding_id for item in findings
                    ),
                )
                records.append(record)
                page_records.append(record)
                global_order += 1
            pages.append(_page_projection(page, tuple(page_records)))
        _bounded_result(
            records,
            exclusions,
            dehyphenation,
            page_classifications,
            publisher_classifications,
            glyph_findings,
        )
        text = "\n\n".join(page.text for page in pages) + "\n"
        return CleanTranscriptV2Artifact.create(
            transcription_result=transcription_result,
            layouts=layouts,
            pages=tuple(pages),
            blocks=tuple(records),
            exclusions=tuple(exclusions),
            dehyphenation_decisions=tuple(dehyphenation),
            page_number_classifications=page_classifications,
            publisher_front_matter=publisher_classifications,
            private_use_glyph_findings=tuple(glyph_findings),
            text=text,
            warnings=tuple(warnings),
            processor_name=self.name,
            processor_version=self.version,
            configuration_digest=configuration.configuration_digest,
        )


def _validate_inputs(
    transcription_result: StructuredTranscriptionResult,
    layouts: tuple[PageLayoutResult, ...],
):
    if not isinstance(transcription_result, StructuredTranscriptionResult):
        raise TypeError(
            "transcription_result must be StructuredTranscriptionResult"
        )
    if not isinstance(layouts, tuple):
        raise TypeError("layouts must be a tuple")
    document = transcription_result.transcription_input.document
    if len(document.pages) > _MAX_PAGES:
        raise CleanTranscriptV2LimitError("document pages exceed limit")
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
    return document, layout_by_page


def _clean_text(
    *,
    block_id: str,
    page_index: int,
    printed_page_label: str | None,
    text: str,
    source_spans: tuple[SourceSpan, ...],
    all_text: tuple[str, ...],
    configuration: CleanTranscriptV2Configuration,
) -> tuple[str, Metadata, tuple[DehyphenationDecision, ...]]:
    decisions: list[DehyphenationDecision] = []

    def replace(match: re.Match[str]) -> str:
        left = match.group("left")
        right = match.group("right")
        joined = (left + right).casefold()
        hyphenated = f"{left}-{right}".casefold()
        joined_evidence = joined in configuration.accepted_joined_forms or any(
            _contains_form(value, joined) for value in all_text
        )
        hyphenated_evidence = (
            hyphenated in configuration.accepted_hyphenated_forms
            or any(_contains_form(value, hyphenated) for value in all_text)
        )
        evidence: list[tuple[str, str]] = []
        if joined in configuration.accepted_joined_forms:
            evidence.append(("accepted_lexical_form", joined))
        if hyphenated in configuration.accepted_hyphenated_forms:
            evidence.append(("accepted_hyphenated_form", hyphenated))
        if any(_contains_form(value, joined) for value in all_text):
            evidence.append(("same_document_joined_form", joined))
        if any(_contains_form(value, hyphenated) for value in all_text):
            evidence.append(("same_document_hyphenated_form", hyphenated))
        if joined_evidence and not hyphenated_evidence:
            outcome = DehyphenationOutcome.JOIN
            replacement = left + right
        elif hyphenated_evidence and not joined_evidence:
            outcome = DehyphenationOutcome.PRESERVE_HYPHEN
            replacement = f"{left}-{right}"
        else:
            outcome = DehyphenationOutcome.PRESERVE_BREAK_CONSERVATIVELY
            replacement = f"{left}- {right}"
            evidence.append(("insufficient_or_conflicting_evidence", "true"))
        decisions.append(
            DehyphenationDecision.create(
                block_id=block_id,
                page_index=page_index,
                printed_page_label=printed_page_label,
                raw_fragment=match.group(0),
                start_offset=match.start(),
                end_offset=match.end(),
                left_fragment=left,
                right_fragment=right,
                outcome=outcome,
                evidence=tuple(evidence),
                source_spans=source_spans,
            )
        )
        return replacement

    control_offsets = tuple(
        str(match.start()) for match in _CONTROL_CHARACTER.finditer(text)
    )
    soft_hyphen_offsets = tuple(
        str(index)
        for index, character in enumerate(text)
        if character == "\u00ad"
    )
    value = _LINE_BREAK_HYPHENATION.sub(replace, text)
    value = _CONTROL_CHARACTER.sub(" ", value).replace("\u00ad", "")
    normalized = _WHITESPACE.sub(" ", value).strip()
    transformations: Metadata = tuple(
        sorted(
            (
                ("control_character_offsets", ",".join(control_offsets)),
                (
                    "dehyphenation_decision_count",
                    str(len(decisions)),
                ),
                ("soft_hyphen_offsets", ",".join(soft_hyphen_offsets)),
                ("unicode_normalization", "none"),
                ("whitespace_normalization", "collapse_unicode_whitespace"),
            )
        )
    )
    return normalized, transformations, tuple(decisions)


def _numeric_candidates(document) -> tuple[_NumericCandidate, ...]:
    result: list[_NumericCandidate] = []
    for page in document.pages:
        for block in page.blocks:
            if block.kind != "text" or block.text is None:
                continue
            value = _basic_clean(block.text).casefold()
            if not _PAGE_NUMBER.fullmatch(value):
                continue
            result.append(
                _NumericCandidate(
                    block_id=block.block_id,
                    page_index=page.page_index,
                    printed_page_label=page.printed_page_label,
                    raw_text=block.text,
                    normalized_value=value,
                    bounding_box=_union_box(block.source_spans),
                    source_spans=block.source_spans,
                    page_width=page.width,
                    page_height=page.height,
                )
            )
    return tuple(result)


def _classify_page_number(
    candidate: _NumericCandidate,
    *,
    protected_ids: set[str],
    recurring_sequence_ids: frozenset[str],
    printed_label_match_count: int,
    configuration: CleanTranscriptV2Configuration,
) -> PageNumberClassification:
    if candidate.block_id in protected_ids:
        outcome = PageNumberOutcome.NOT_PAGE_NUMBER
        method = PageNumberMethod.TYPED_CONTENT
        evidence = (("typed_structured_content", "true"),)
    elif not _candidate_is_margin(candidate, configuration):
        outcome = PageNumberOutcome.NOT_PAGE_NUMBER
        method = PageNumberMethod.OUTSIDE_MARGIN
        evidence = (("margin_candidate", "false"),)
    elif (
        candidate.printed_page_label is not None
        and _basic_clean(candidate.printed_page_label).casefold()
        == candidate.normalized_value
        and printed_label_match_count == 1
    ):
        outcome = PageNumberOutcome.PAGE_NUMBER
        method = PageNumberMethod.PRINTED_PAGE_LABEL
        evidence = (("printed_page_label", candidate.printed_page_label),)
    elif candidate.block_id in recurring_sequence_ids:
        outcome = PageNumberOutcome.PAGE_NUMBER
        method = PageNumberMethod.RECURRING_GEOMETRY_SEQUENCE
        evidence = (("recurring_geometry_sequence", "true"),)
    else:
        outcome = PageNumberOutcome.UNRESOLVED
        method = PageNumberMethod.INSUFFICIENT_EVIDENCE
        evidence = (("insufficient_page_number_evidence", "true"),)
    return PageNumberClassification.create(
        block_id=candidate.block_id,
        page_index=candidate.page_index,
        printed_page_label=candidate.printed_page_label,
        raw_text=candidate.raw_text,
        normalized_value=candidate.normalized_value,
        bounding_box=candidate.bounding_box,
        outcome=outcome,
        method=method,
        evidence=evidence,
        source_spans=candidate.source_spans,
    )


def _recurring_sequence_ids(
    candidates: tuple[_NumericCandidate, ...],
    configuration: CleanTranscriptV2Configuration,
) -> frozenset[str]:
    groups: dict[tuple[str, int], list[tuple[_NumericCandidate, int]]] = (
        defaultdict(list)
    )
    tolerance = configuration.page_number_horizontal_tolerance_fraction
    for candidate in candidates:
        if not _candidate_is_margin(candidate, configuration):
            continue
        number = _page_ordinal(candidate.normalized_value)
        box = candidate.bounding_box
        if number is None or box is None:
            continue
        side = "top" if box[3] <= candidate.page_height / 2.0 else "bottom"
        center_fraction = ((box[0] + box[2]) / 2.0) / candidate.page_width
        bucket = round(center_fraction / tolerance) if tolerance else 0
        groups[(side, bucket)].append((candidate, number))
    accepted: set[str] = set()
    for values in groups.values():
        ordered = sorted(values, key=lambda item: item[0].page_index)
        run: list[tuple[_NumericCandidate, int]] = []
        for item in ordered:
            if not run or (
                item[0].page_index == run[-1][0].page_index + 1
                and item[1] == run[-1][1] + 1
            ):
                run.append(item)
            else:
                if len(run) >= configuration.minimum_page_sequence_length:
                    accepted.update(candidate.block_id for candidate, _ in run)
                run = [item]
        if len(run) >= configuration.minimum_page_sequence_length:
            accepted.update(candidate.block_id for candidate, _ in run)
    return frozenset(accepted)


def _publisher_classifications(
    transcription_result: StructuredTranscriptionResult,
    configuration: CleanTranscriptV2Configuration,
) -> tuple[PublisherFrontMatterClassification, ...]:
    document = transcription_result.transcription_input.document
    structure = transcription_result.transcription_input.structure_analysis
    front_ids = {
        block_id
        for node in structure.nodes
        if node.kind is StructureKind.FRONT_MATTER
        for block_id in node.source_block_ids
    }
    result: list[PublisherFrontMatterClassification] = []
    for page in document.pages:
        for block in page.blocks:
            if block.kind != "text" or block.text is None:
                continue
            structure_front_matter = block.block_id in front_ids
            kind, signal = _publisher_kind(
                block.text,
                structure_front_matter=structure_front_matter,
                first_page=page.page_index == 0,
            )
            if kind is None:
                continue
            disposition = (
                ClassificationDisposition.EXCLUDED
                if kind in configuration.excluded_publisher_front_matter
                else ClassificationDisposition.INCLUDED
            )
            result.append(
                PublisherFrontMatterClassification.create(
                    block_id=block.block_id,
                    page_index=page.page_index,
                    kind=kind,
                    disposition=disposition,
                    evidence=(("lexical_signal", signal),),
                    source_spans=block.source_spans,
                )
            )
    return tuple(result)


def _publisher_kind(
    text: str,
    *,
    structure_front_matter: bool,
    first_page: bool,
) -> tuple[PublisherFrontMatterKind | None, str]:
    value = _basic_clean(text).casefold()
    strong_signals = (
        (
            PublisherFrontMatterKind.LICENSING,
            (
                "copyright",
                "all rights reserved",
                "creative commons",
                "licence",
                "license",
            ),
        ),
        (
            PublisherFrontMatterKind.CITATION,
            ("cite this article", "recommended citation", "doi:"),
        ),
        (
            PublisherFrontMatterKind.NOTICE,
            ("publisher's note", "published by", "terms of use"),
        ),
    )
    for kind, candidates in strong_signals:
        for signal in candidates:
            if signal in value:
                return kind, signal
    if first_page or structure_front_matter:
        if "issn" in value or ("volume" in value and "issue" in value):
            return PublisherFrontMatterKind.MASTHEAD, "masthead-identifiers"
        for signal in ("cover image", "front cover"):
            if signal in value:
                return PublisherFrontMatterKind.COVER, signal
    if structure_front_matter and "publisher" in value:
        return PublisherFrontMatterKind.UNRECOGNIZED, "publisher"
    return None, ""


def _private_use_findings(
    *,
    block_id: str,
    page_index: int,
    printed_page_label: str | None,
    text: str,
    source_spans: tuple[SourceSpan, ...],
) -> tuple[PrivateUseGlyphFinding, ...]:
    return tuple(
        PrivateUseGlyphFinding.create(
            block_id=block_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            character_offset=index,
            raw_character=character,
            source_spans=source_spans,
        )
        for index, character in enumerate(text)
        if unicodedata.category(character) == "Co"
    )


def _repeated_margin_keys(
    transcription_result: StructuredTranscriptionResult,
    layouts: tuple[PageLayoutResult, ...],
    configuration: CleanTranscriptV2Configuration,
) -> frozenset[str]:
    document = transcription_result.transcription_input.document
    layout_by_page = {layout.page_index: layout for layout in layouts}
    pages_by_key: dict[str, set[int]] = defaultdict(set)
    for page in document.pages:
        block_by_id = {block.block_id: block for block in page.blocks}
        for block_id in layout_by_page[page.page_index].raw_block_ids:
            block = block_by_id[block_id]
            if block.kind != "text" or block.text is None:
                continue
            if not _is_margin(block.source_spans, page.height, configuration):
                continue
            clean = _basic_clean(block.text)
            if clean and not _PAGE_NUMBER.fullmatch(clean.casefold()):
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


def _page_projection(page, records) -> CleanTranscriptV2Page:
    label = (
        "none"
        if page.printed_page_label is None
        else page.printed_page_label.replace('"', "'")
    )
    marker = f'[[PAGE physical={page.page_index + 1} printed="{label}"]]'
    body = "\n\n".join(item.clean_text for item in records)
    text = marker if not body else f"{marker}\n\n{body}"
    return CleanTranscriptV2Page.create(
        page_index=page.page_index,
        printed_page_label=page.printed_page_label,
        block_record_ids=tuple(item.record_id for item in records),
        text=text,
    )


def _text_block_order(
    blocks, proposed_order: tuple[str, ...]
) -> tuple[str, ...]:
    block_by_id = {block.block_id: block for block in blocks}
    text_ids = tuple(
        block.block_id
        for block in blocks
        if block.kind == "text" and block.text is not None
    )
    ordered = tuple(
        block_id
        for block_id in proposed_order
        if block_id in block_by_id
        and block_by_id[block_id].kind == "text"
        and block_by_id[block_id].text is not None
    )
    return (
        *ordered,
        *(block_id for block_id in text_ids if block_id not in ordered),
    )


def _basic_clean(text: str) -> str:
    return _WHITESPACE.sub(
        " ", _CONTROL_CHARACTER.sub(" ", text).replace("\u00ad", "")
    ).strip()


def _contains_form(text: str, form: str) -> bool:
    value = _basic_clean(text).casefold()
    start = 0
    while True:
        index = value.find(form, start)
        if index < 0:
            return False
        left_ok = index == 0 or not _WORD_CHARACTER.fullmatch(value[index - 1])
        end = index + len(form)
        right_ok = end == len(value) or not _WORD_CHARACTER.fullmatch(
            value[end]
        )
        if left_ok and right_ok:
            return True
        start = index + 1


def _candidate_is_margin(
    candidate: _NumericCandidate,
    configuration: CleanTranscriptV2Configuration,
) -> bool:
    box = candidate.bounding_box
    if box is None:
        return False
    return box[
        3
    ] <= candidate.page_height * configuration.top_margin_fraction or box[
        1
    ] >= candidate.page_height * (1.0 - configuration.bottom_margin_fraction)


def _is_margin(
    spans: tuple[SourceSpan, ...],
    page_height: float,
    configuration: CleanTranscriptV2Configuration,
) -> bool:
    box = _union_box(spans)
    if box is None:
        return False
    return box[3] <= page_height * configuration.top_margin_fraction or box[
        1
    ] >= page_height * (1.0 - configuration.bottom_margin_fraction)


def _union_box(spans: tuple[SourceSpan, ...]) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box for span in spans if span.bounding_box is not None
    )
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _page_ordinal(value: str) -> int | None:
    if value.isdecimal():
        return int(value)
    roman = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    previous = 0
    for character in reversed(value.casefold()):
        current = roman.get(character)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total or None


def _margin_key(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).casefold()
    return _DIGITS.sub("#", normalized)


def _span_parts(spans: tuple[SourceSpan, ...]) -> tuple[object, ...]:
    return tuple(
        (*span.identity_parts(), span.printed_page_label) for span in spans
    )


def _normalized_forms(
    name: str, values: tuple[str, ...], *, hyphen: bool
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple")
    result = tuple(sorted({value.strip().casefold() for value in values}))
    if any(
        not value
        or _WHITESPACE.search(value)
        or (hyphen and value.count("-") != 1)
        or (not hyphen and "-" in value)
        for value in result
    ):
        raise ValueError(f"{name} contains an invalid lexical form")
    return result


def _metadata_count(metadata: Metadata, key: str) -> bool:
    return any(item_key == key and bool(value) for item_key, value in metadata)


def _require_unique(name: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")


def _bounded_result(
    records: list[CleanTranscriptV2Block],
    exclusions: list[CleanTranscriptV2Exclusion],
    dehyphenation: list[DehyphenationDecision],
    page_classifications: tuple[PageNumberClassification, ...],
    publisher_classifications: tuple[PublisherFrontMatterClassification, ...],
    glyph_findings: list[PrivateUseGlyphFinding],
) -> None:
    for values, limit in (
        (records, _MAX_BLOCKS),
        (exclusions, _MAX_EXCLUSIONS),
        (dehyphenation, _MAX_DECISIONS),
        (page_classifications, _MAX_DECISIONS),
        (publisher_classifications, _MAX_DECISIONS),
        (glyph_findings, _MAX_FINDINGS),
    ):
        if len(values) > limit:
            raise CleanTranscriptV2LimitError(
                "transcript-v2 projection exceeds an object limit"
            )
