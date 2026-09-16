from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedDocument,
    IngestionWarning,
    Metadata,
    SourceSpan,
    TableOfContentsEntry,
    WarningSeverity,
)
from projectkoios.ingestion.protocols import PageLayoutProcessor
from projectkoios.ingestion.structure import (
    StructureAnalysis,
    StructureEvidenceStatus,
    StructureKind,
    StructureNode,
)

ARTICLE_STRUCTURE_PROCESSOR_VERSION = "1"
_MAX_PAGES = 512
_MAX_INPUT_BLOCKS = 16_384
_MAX_TEXT_BLOCKS = 8_192
_MAX_NODES = 4_096
_MAX_WARNINGS = 4_096
_MAX_TEXT_CHARACTERS = 5_000_000
_MAX_HEADING_CHARACTERS = 512
_MAX_ABSTRACT_BLOCKS = 64
_MAX_BIBLIOGRAPHY_ENTRIES = 2_048
_NUMBERED_HEADING = re.compile(
    r"^\s*(?P<label>\d+(?:\.\d+)*)(?:[.)])?\s+(?P<title>\S.*)\s*$"
)
_APPENDIX_HEADING = re.compile(
    r"^\s*appendix(?:\s+(?P<label>[A-Za-z0-9]+))?"
    r"(?:\s*[:.\-]?\s*(?P<title>.*))?$",
    re.IGNORECASE,
)
_AUTHOR_LINE = re.compile(
    r"^\s*(?:by|authors?)\s*[:\-]?\s*(?P<names>\S.*)$",
    re.IGNORECASE,
)
_BIBLIOGRAPHY_ENTRY = re.compile(
    r"^\s*(?:\[\d+\]|\d+[.)]\s+|[A-Z][^\n]{0,100}\(\d{4}[a-z]?\))"
)
_KNOWN_SECTIONS = frozenset(
    {
        "acknowledgment",
        "acknowledgments",
        "acknowledgement",
        "acknowledgements",
        "conclusion",
        "conclusions",
        "discussion",
        "experimental",
        "introduction",
        "materials and methods",
        "methods",
        "results",
        "results and discussion",
    }
)
_BIBLIOGRAPHY_TITLES = frozenset(
    {"bibliography", "literature cited", "references"}
)


class ArticleStructureLimitError(ValueError):
    """Raised before article-structure analysis exceeds a configured bound."""


@dataclass(frozen=True)
class ArticleStructureConfiguration:
    max_pages: int = _MAX_PAGES
    max_input_blocks: int = _MAX_INPUT_BLOCKS
    max_text_blocks: int = _MAX_TEXT_BLOCKS
    max_nodes: int = _MAX_NODES
    max_warnings: int = _MAX_WARNINGS
    max_text_characters: int = _MAX_TEXT_CHARACTERS
    max_heading_characters: int = _MAX_HEADING_CHARACTERS
    max_abstract_blocks: int = _MAX_ABSTRACT_BLOCKS
    max_bibliography_entries: int = _MAX_BIBLIOGRAPHY_ENTRIES
    fallback_title_top_ratio: float = 0.3

    def __post_init__(self) -> None:
        for name, maximum in (
            ("max_pages", _MAX_PAGES),
            ("max_input_blocks", _MAX_INPUT_BLOCKS),
            ("max_text_blocks", _MAX_TEXT_BLOCKS),
            ("max_nodes", _MAX_NODES),
            ("max_warnings", _MAX_WARNINGS),
            ("max_text_characters", _MAX_TEXT_CHARACTERS),
            ("max_heading_characters", _MAX_HEADING_CHARACTERS),
            ("max_abstract_blocks", _MAX_ABSTRACT_BLOCKS),
            ("max_bibliography_entries", _MAX_BIBLIOGRAPHY_ENTRIES),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
            if value > maximum:
                raise ArticleStructureLimitError(
                    f"{name} exceeds the implementation maximum ({maximum})"
                )
        ratio = self.fallback_title_top_ratio
        if isinstance(ratio, bool) or not isinstance(ratio, int | float):
            raise ValueError("fallback_title_top_ratio must be finite")
        normalized = float(ratio)
        if not math.isfinite(normalized) or not 0.0 < normalized <= 1.0:
            raise ValueError(
                "fallback_title_top_ratio must be greater than zero and "
                "no greater than one"
            )
        object.__setattr__(self, "fallback_title_top_ratio", normalized)

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "article-structure-configuration",
            self.max_pages,
            self.max_input_blocks,
            self.max_text_blocks,
            self.max_nodes,
            self.max_warnings,
            self.max_text_characters,
            self.max_heading_characters,
            self.max_abstract_blocks,
            self.max_bibliography_entries,
            self.fallback_title_top_ratio,
        )


@dataclass(frozen=True)
class _TextEvidence:
    block: ExtractedBlock
    page_index: int
    page_height: float
    source_key: tuple[int, int, int]
    reading_confidence: float

    @property
    def text(self) -> str:
        assert self.block.text is not None
        return self.block.text

    @property
    def normalized_text(self) -> str:
        return _normalized_text(self.text)

    @property
    def bounding_box(self) -> BoundingBox | None:
        boxes = tuple(
            span.bounding_box
            for span in self.block.source_spans
            if span.bounding_box is not None
        )
        if len(boxes) != len(self.block.source_spans) or not boxes:
            return None
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )


@dataclass
class _Proposal:
    key: str
    kind: StructureKind
    source_spans: tuple[SourceSpan, ...]
    source_block_ids: tuple[str, ...]
    source_key: tuple[int, int, int]
    evidence_type: str
    confidence: float
    title: str | None = None
    label: str | None = None
    heading_level: int | None = None
    heading_confidence: float | None = None
    reading_order: int | None = None
    reading_order_confidence: float | None = None
    evidence_status: StructureEvidenceStatus = StructureEvidenceStatus.PROPOSED
    evidence: Metadata = ()
    parent_key: str | None = None
    warning_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _WarningProposal:
    key: str
    code: str
    message: str
    proposal_keys: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    object_ids: tuple[str, ...] = ()
    evidence: Metadata = ()


@dataclass(frozen=True)
class _Heading:
    kind: StructureKind
    level: int
    label: str | None
    title: str
    evidence_type: str
    confidence: float


class DeterministicArticleStructureAnalyzer:
    """Propose bounded article structure from exact text/layout evidence."""

    name = "deterministic-article-structure"
    version = ARTICLE_STRUCTURE_PROCESSOR_VERSION

    def __init__(
        self,
        configuration: ArticleStructureConfiguration | None = None,
        *,
        layout_processor: PageLayoutProcessor | None = None,
    ) -> None:
        self.configuration = configuration or ArticleStructureConfiguration()
        self.layout_processor = (
            layout_processor or DeterministicLayoutProcessor()
        )

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def analyze(self, document: ExtractedDocument) -> StructureAnalysis:
        layouts = self.layout_processor.analyze(document)
        return self.analyze_with_layout(document, layouts)

    def analyze_with_layout(
        self,
        document: ExtractedDocument,
        layouts: tuple[PageLayoutResult, ...],
    ) -> StructureAnalysis:
        _validate_input(document, layouts, self.configuration)
        text_evidence = _ordered_text_evidence(
            document, layouts, self.configuration
        )
        proposals, warning_proposals = _propose(
            document,
            layouts,
            text_evidence,
            self.configuration,
        )
        if len(proposals) > self.configuration.max_nodes:
            raise ArticleStructureLimitError("proposed nodes exceed max_nodes")
        if len(warning_proposals) > self.configuration.max_warnings:
            raise ArticleStructureLimitError(
                "structure warnings exceed max_warnings"
            )
        nodes, warnings = _materialize(proposals, warning_proposals)
        return StructureAnalysis.create(
            source=document.source,
            nodes=nodes,
            warnings=warnings,
            layout_result_ids=tuple(layout.result_id for layout in layouts),
            input_block_ids=tuple(
                block.block_id
                for page in document.pages
                for block in page.blocks
            ),
            processor_name=self.name,
            processor_version=self.version,
            configuration_digest=self.configuration_digest,
        )


def _validate_input(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    configuration: ArticleStructureConfiguration,
) -> None:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("document must be ExtractedDocument")
    if not isinstance(layouts, tuple):
        raise TypeError("layouts must be an immutable tuple")
    if len(document.pages) > configuration.max_pages:
        raise ArticleStructureLimitError("document pages exceed max_pages")
    if len(layouts) != len(document.pages):
        raise ValueError("one layout result is required per document page")
    if any(not isinstance(layout, PageLayoutResult) for layout in layouts):
        raise TypeError("layouts must contain PageLayoutResult values")
    total_input_blocks = 0
    input_block_ids: set[str] = set()
    total_blocks = 0
    total_text = 0
    for page, layout in zip(document.pages, layouts, strict=True):
        if (
            layout.source_id != document.source.source_id
            or layout.source_blob_id != document.source.blob_id
            or layout.source_content_hash != document.source.content_hash
            or layout.page_index != page.page_index
            or layout.page_width != page.width
            or layout.page_height != page.height
            or layout.coordinate_system != page.coordinate_system
            or layout.rotation_degrees != page.rotation_degrees
        ):
            raise ValueError("layout result does not match its document page")
        expected_raw = tuple(
            (block.block_id, block.kind, block.source_spans)
            for block in page.blocks
        )
        actual_raw = tuple(
            (item.block_id, item.kind, item.source_spans)
            for item in layout.raw_blocks
        )
        if expected_raw != actual_raw:
            raise ValueError("layout raw blocks do not match the document page")
        total_input_blocks += len(page.blocks)
        for block in page.blocks:
            if block.block_id in input_block_ids:
                raise ValueError("document block IDs must be globally unique")
            input_block_ids.add(block.block_id)
        if total_input_blocks > configuration.max_input_blocks:
            raise ArticleStructureLimitError(
                "input blocks exceed max_input_blocks"
            )
        for block in page.blocks:
            if block.kind == "text" and isinstance(block.text, str):
                total_blocks += 1
                total_text += len(block.text)
                if total_blocks > configuration.max_text_blocks:
                    raise ArticleStructureLimitError(
                        "text blocks exceed max_text_blocks"
                    )
                if total_text > configuration.max_text_characters:
                    raise ArticleStructureLimitError(
                        "text exceeds max_text_characters"
                    )


def _ordered_text_evidence(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    configuration: ArticleStructureConfiguration,
) -> tuple[_TextEvidence, ...]:
    evidence: list[_TextEvidence] = []
    for page_order, (page, layout) in enumerate(
        zip(document.pages, layouts, strict=True)
    ):
        blocks = {block.block_id: block for block in page.blocks}
        raw_order = {
            block.block_id: index for index, block in enumerate(page.blocks)
        }
        proposed = set(layout.proposed_order)
        ordered_ids = list(layout.proposed_order)
        ordered_ids.extend(
            block.block_id
            for block in page.blocks
            if block.kind == "text" and block.block_id not in proposed
        )
        for local_order, block_id in enumerate(ordered_ids):
            block = blocks[block_id]
            if not isinstance(block.text, str) or not block.text.strip():
                continue
            if len(block.text) > configuration.max_text_characters:
                raise ArticleStructureLimitError(
                    "text block exceeds max_text_characters"
                )
            reading_confidence = min(
                block.confidence,
                layout.confidence if block_id in proposed else 0.35,
            )
            evidence.append(
                _TextEvidence(
                    block=block,
                    page_index=page.page_index,
                    page_height=page.height,
                    source_key=(
                        page_order,
                        local_order,
                        raw_order[block_id],
                    ),
                    reading_confidence=reading_confidence,
                )
            )
    return tuple(evidence)


def _propose(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    text_evidence: tuple[_TextEvidence, ...],
    configuration: ArticleStructureConfiguration,
) -> tuple[list[_Proposal], list[_WarningProposal]]:
    proposals: list[_Proposal] = []
    warnings: list[_WarningProposal] = []
    if not text_evidence:
        warnings.append(
            _WarningProposal(
                key="empty-document",
                code="structure.no_text_evidence",
                message="No text evidence is available for article structure",
                proposal_keys=(),
                source_spans=(),
            )
        )
        return proposals, warnings
    root = _Proposal(
        key="document",
        kind=StructureKind.DOCUMENT,
        source_spans=(text_evidence[0].block.source_spans[0],),
        source_block_ids=(text_evidence[0].block.block_id,),
        source_key=(-1, -1, -1),
        evidence_type="exact_source_document",
        confidence=1.0,
        evidence_status=StructureEvidenceStatus.OBSERVED,
        evidence=(("document_id", document.document_id),),
    )
    proposals.append(root)
    consumed: set[str] = set()
    front: list[_Proposal] = []
    title = _title_proposal(document, text_evidence, configuration, warnings)
    if title is not None:
        front.append(title)
        consumed.update(title.source_block_ids)
    author = _author_proposal(text_evidence, consumed)
    if author is not None:
        front.append(author)
        consumed.update(author.source_block_ids)
    abstract = _abstract_proposal(
        text_evidence, consumed, configuration.max_abstract_blocks
    )
    if abstract is not None:
        front.append(abstract)
        consumed.update(abstract.source_block_ids)
    keywords = _keywords_proposal(text_evidence, consumed)
    if keywords is not None:
        front.append(keywords)
        consumed.update(keywords.source_block_ids)
    if front:
        front_spans = _ordered_unique_spans(
            span for proposal in front for span in proposal.source_spans
        )
        front_blocks = tuple(
            block_id
            for proposal in front
            for block_id in proposal.source_block_ids
        )
        front_container = _Proposal(
            key="front-matter",
            kind=StructureKind.FRONT_MATTER,
            source_spans=front_spans,
            source_block_ids=front_blocks,
            source_key=(-1, 0, 0),
            evidence_type="grouped_front_matter",
            confidence=min(item.confidence for item in front),
            evidence_status=StructureEvidenceStatus.PROPOSED,
            parent_key="document",
        )
        proposals.append(front_container)
        for proposal in front:
            proposal.parent_key = "front-matter"
        proposals.extend(front)
    section_proposals, section_warnings = _section_proposals(
        text_evidence, consumed, configuration
    )
    _apply_table_of_contents(document.table_of_contents, section_proposals)
    _assign_section_parents(section_proposals)
    proposals.extend(section_proposals)
    warnings.extend(section_warnings)
    for layout in layouts:
        if not layout.warnings:
            continue
        spans = tuple(
            span
            for reference in layout.input_text_blocks[:1]
            for span in reference.source_spans[:1]
        )
        warnings.append(
            _WarningProposal(
                key=f"layout:{layout.result_id}",
                code="structure.layout_order_uncertain",
                message="Article structure retains uncertain layout order",
                proposal_keys=(),
                source_spans=spans,
                object_ids=(layout.result_id,),
                evidence=(
                    ("layout_result_id", layout.result_id),
                    ("layout_warning_count", str(len(layout.warnings))),
                ),
            )
        )
    ordered_content = sorted(
        (
            item
            for item in proposals
            if item.key not in {"document", "front-matter"}
        ),
        key=lambda item: item.source_key,
    )
    for reading_order, proposal in enumerate(ordered_content):
        proposal.reading_order = reading_order
        if proposal.reading_order_confidence is None:
            proposal.reading_order_confidence = 0.5
    if len(proposals) > configuration.max_nodes:
        raise ArticleStructureLimitError("proposed nodes exceed max_nodes")
    return proposals, warnings


def _title_proposal(
    document: ExtractedDocument,
    text_evidence: tuple[_TextEvidence, ...],
    configuration: ArticleStructureConfiguration,
    warnings: list[_WarningProposal],
) -> _Proposal | None:
    metadata_titles = tuple(
        value
        for key, value in document.metadata
        if key.casefold() == "title" and value.strip()
    )
    for metadata_title in metadata_titles:
        normalized = _normalized_text(metadata_title)
        for item in text_evidence:
            if item.source_key[0] == 0 and item.normalized_text == normalized:
                return _proposal_from_evidence(
                    key="title",
                    kind=StructureKind.TITLE,
                    items=(item,),
                    evidence_type="metadata_and_exact_text",
                    confidence=0.98,
                    title=item.text.strip(),
                    heading_level=0,
                    heading_confidence=0.98,
                    evidence=(("metadata_title", metadata_title),),
                )
    first = text_evidence[0]
    text = first.text.strip()
    box = first.bounding_box
    near_top = box is None or (
        box[1] <= first.page_height * configuration.fallback_title_top_ratio
    )
    if (
        first.source_key[0] == 0
        and near_top
        and len(text) <= configuration.max_heading_characters
        and _heading(text, configuration.max_heading_characters) is None
        and _front_kind(text) is None
        and _AUTHOR_LINE.fullmatch(text) is None
    ):
        proposal = _proposal_from_evidence(
            key="title",
            kind=StructureKind.TITLE,
            items=(first,),
            evidence_type="first_page_top_text_fallback",
            confidence=0.45,
            title=text,
            heading_level=0,
            heading_confidence=0.45,
            evidence=(("fallback", "first_page_top_text"),),
        )
        proposal.warning_keys.append("fallback-title")
        warnings.append(
            _WarningProposal(
                key="fallback-title",
                code="structure.fallback_title",
                message="Title is a bounded first-page fallback proposal",
                proposal_keys=(proposal.key,),
                source_spans=proposal.source_spans,
                evidence=proposal.evidence,
            )
        )
        return proposal
    warnings.append(
        _WarningProposal(
            key="missing-title",
            code="structure.title_not_identified",
            message="No source-backed article title was identified",
            proposal_keys=(),
            source_spans=(first.block.source_spans[0],),
        )
    )
    return None


def _author_proposal(
    evidence: tuple[_TextEvidence, ...], consumed: set[str]
) -> _Proposal | None:
    for item in evidence[:16]:
        if item.block.block_id in consumed:
            continue
        match = _AUTHOR_LINE.fullmatch(item.text.strip())
        if match is None:
            if _front_kind(item.text) is not None or _heading(item.text, 512):
                break
            continue
        return _proposal_from_evidence(
            key=f"author:{item.block.block_id}",
            kind=StructureKind.AUTHOR,
            items=(item,),
            evidence_type="explicit_author_prefix",
            confidence=0.95,
            title=match.group("names").strip(),
            evidence_status=StructureEvidenceStatus.OBSERVED,
        )
    return None


def _abstract_proposal(
    evidence: tuple[_TextEvidence, ...],
    consumed: set[str],
    max_blocks: int,
) -> _Proposal | None:
    for index, item in enumerate(evidence):
        if item.block.block_id in consumed:
            continue
        normalized = item.normalized_text
        if normalized != "abstract" and not normalized.startswith("abstract:"):
            continue
        selected = [item]
        if normalized == "abstract":
            for following in evidence[index + 1 :]:
                if following.block.block_id in consumed:
                    continue
                if len(selected) >= max_blocks:
                    break
                if _front_kind(following.text) == StructureKind.KEYWORDS:
                    break
                if _heading(following.text, 512) is not None:
                    break
                selected.append(following)
        return _proposal_from_evidence(
            key=f"abstract:{item.block.block_id}",
            kind=StructureKind.ABSTRACT,
            items=tuple(selected),
            evidence_type="explicit_abstract_heading",
            confidence=0.95,
            title="Abstract",
            heading_level=1,
            heading_confidence=0.98,
        )
    return None


def _keywords_proposal(
    evidence: tuple[_TextEvidence, ...], consumed: set[str]
) -> _Proposal | None:
    for item in evidence:
        if item.block.block_id in consumed:
            continue
        normalized = item.normalized_text
        if not (
            normalized.startswith("keywords:")
            or normalized.startswith("keyword:")
        ):
            continue
        _, _, values = item.text.partition(":")
        return _proposal_from_evidence(
            key=f"keywords:{item.block.block_id}",
            kind=StructureKind.KEYWORDS,
            items=(item,),
            evidence_type="explicit_keywords_prefix",
            confidence=0.98,
            title=values.strip() or item.text.strip(),
            evidence_status=StructureEvidenceStatus.OBSERVED,
        )
    return None


def _section_proposals(
    evidence: tuple[_TextEvidence, ...],
    consumed: set[str],
    configuration: ArticleStructureConfiguration,
) -> tuple[list[_Proposal], list[_WarningProposal]]:
    proposals: list[_Proposal] = []
    warnings: list[_WarningProposal] = []
    bibliography: _Proposal | None = None
    total_bibliography_entries = 0
    current_bibliography_entries = 0
    for item in evidence:
        if item.block.block_id in consumed:
            continue
        text = item.text.strip()
        if bibliography is not None:
            appendix = _appendix_heading(text)
            if appendix is None:
                if (
                    total_bibliography_entries
                    >= configuration.max_bibliography_entries
                ):
                    raise ArticleStructureLimitError(
                        "bibliography entries exceed their configured limit"
                    )
                total_bibliography_entries += 1
                current_bibliography_entries += 1
                entry = _proposal_from_evidence(
                    key=f"bibliography-entry:{item.block.block_id}",
                    kind=StructureKind.BIBLIOGRAPHY_ENTRY,
                    items=(item,),
                    evidence_type=(
                        "bibliography_region_and_citation_pattern"
                        if _BIBLIOGRAPHY_ENTRY.match(text)
                        else "bibliography_region_observation"
                    ),
                    confidence=(
                        0.9 if _BIBLIOGRAPHY_ENTRY.match(text) else 0.65
                    ),
                    title=text,
                    evidence_status=StructureEvidenceStatus.OBSERVED,
                )
                entry.parent_key = bibliography.key
                proposals.append(entry)
                continue
            if current_bibliography_entries == 0:
                _record_empty_bibliography(bibliography, warnings)
            bibliography = None
            current_bibliography_entries = 0
        heading = _heading(text, configuration.max_heading_characters)
        if heading is None:
            continue
        proposal = _proposal_from_evidence(
            key=f"heading:{item.block.block_id}",
            kind=heading.kind,
            items=(item,),
            evidence_type=heading.evidence_type,
            confidence=heading.confidence,
            title=heading.title,
            label=heading.label,
            heading_level=heading.level,
            heading_confidence=heading.confidence,
        )
        proposals.append(proposal)
        if heading.kind is StructureKind.BIBLIOGRAPHY:
            bibliography = proposal
            current_bibliography_entries = 0
    if bibliography is not None and current_bibliography_entries == 0:
        _record_empty_bibliography(bibliography, warnings)
    return proposals, warnings


def _record_empty_bibliography(
    bibliography: _Proposal,
    warnings: list[_WarningProposal],
) -> None:
    warning_key = f"empty-bibliography:{bibliography.key}"
    bibliography.warning_keys.append(warning_key)
    warnings.append(
        _WarningProposal(
            key=warning_key,
            code="structure.empty_bibliography",
            message="Bibliography heading has no observed entry blocks",
            proposal_keys=(bibliography.key,),
            source_spans=bibliography.source_spans,
        )
    )


def _apply_table_of_contents(
    entries: tuple[TableOfContentsEntry, ...], proposals: list[_Proposal]
) -> None:
    for entry in entries:
        normalized_title = _normalized_text(entry.title)
        candidates = [
            proposal
            for proposal in proposals
            if proposal.title is not None
            and _normalized_text(proposal.title) == normalized_title
            and (
                entry.destination is None
                or proposal.source_spans[0].page_index
                == entry.destination.page_index
            )
        ]
        if len(candidates) != 1:
            continue
        proposal = candidates[0]
        proposal.evidence_type = "text_and_table_of_contents"
        proposal.confidence = max(proposal.confidence, 0.98)
        proposal.heading_confidence = max(
            proposal.heading_confidence or 0.0, 0.98
        )
        proposal.heading_level = entry.level
        proposal.evidence = proposal.evidence + (
            ("table_of_contents_entry_id", entry.entry_id),
        )


def _assign_section_parents(proposals: list[_Proposal]) -> None:
    headings = [
        proposal
        for proposal in proposals
        if proposal.kind is not StructureKind.BIBLIOGRAPHY_ENTRY
    ]
    headings.sort(key=lambda proposal: proposal.source_key)
    stack: list[_Proposal] = []
    for proposal in headings:
        level = proposal.heading_level or 1
        while stack and (stack[-1].heading_level or 1) >= level:
            stack.pop()
        proposal.parent_key = stack[-1].key if stack else "document"
        stack.append(proposal)


def _materialize(
    proposals: list[_Proposal],
    warning_proposals: list[_WarningProposal],
) -> tuple[tuple[StructureNode, ...], tuple[IngestionWarning, ...]]:
    base_nodes = {
        proposal.key: _node_from_proposal(proposal) for proposal in proposals
    }
    children: dict[str, list[str]] = {
        proposal.key: [] for proposal in proposals
    }
    for proposal in proposals:
        if proposal.parent_key is not None:
            if proposal.parent_key not in base_nodes:
                raise ValueError("structure proposal parent is unresolved")
            children[proposal.parent_key].append(
                base_nodes[proposal.key].node_id
            )
    warnings: list[IngestionWarning] = []
    warning_ids_by_key: dict[str, str] = {}
    for warning in warning_proposals:
        if any(key not in base_nodes for key in warning.proposal_keys):
            raise ValueError("structure warning proposal is unresolved")
        object_ids = warning.object_ids + tuple(
            base_nodes[key].node_id for key in warning.proposal_keys
        )
        if len(set(object_ids)) != len(object_ids):
            raise ValueError("structure warning object IDs are duplicated")
        value = IngestionWarning.create(
            code=warning.code,
            severity=WarningSeverity.WARNING,
            message=warning.message,
            object_ids=object_ids,
            source_spans=warning.source_spans,
            evidence=warning.evidence,
        )
        warnings.append(value)
        warning_ids_by_key[warning.key] = value.warning_id
    nodes: list[StructureNode] = []
    for proposal in proposals:
        parent_id = (
            base_nodes[proposal.parent_key].node_id
            if proposal.parent_key is not None
            else None
        )
        if any(key not in warning_ids_by_key for key in proposal.warning_keys):
            raise ValueError("structure node warning proposal is unresolved")
        warning_ids = tuple(
            warning_ids_by_key[key] for key in proposal.warning_keys
        )
        nodes.append(
            replace(
                base_nodes[proposal.key],
                parent_id=parent_id,
                child_ids=tuple(children[proposal.key]),
                warning_ids=warning_ids,
            )
        )
    return tuple(nodes), tuple(warnings)


def _node_from_proposal(proposal: _Proposal) -> StructureNode:
    return StructureNode.create(
        kind=proposal.kind,
        source_spans=proposal.source_spans,
        evidence_type=proposal.evidence_type,
        confidence=proposal.confidence,
        label=proposal.label,
        title=proposal.title,
        evidence=proposal.evidence,
        source_block_ids=proposal.source_block_ids,
        heading_level=proposal.heading_level,
        reading_order=proposal.reading_order,
        heading_confidence=proposal.heading_confidence,
        reading_order_confidence=proposal.reading_order_confidence,
        evidence_status=proposal.evidence_status,
    )


def _proposal_from_evidence(
    *,
    key: str,
    kind: StructureKind,
    items: tuple[_TextEvidence, ...],
    evidence_type: str,
    confidence: float,
    title: str | None = None,
    label: str | None = None,
    heading_level: int | None = None,
    heading_confidence: float | None = None,
    evidence_status: StructureEvidenceStatus = StructureEvidenceStatus.PROPOSED,
    evidence: Metadata = (),
) -> _Proposal:
    return _Proposal(
        key=key,
        kind=kind,
        source_spans=_ordered_unique_spans(
            span for item in items for span in item.block.source_spans
        ),
        source_block_ids=tuple(item.block.block_id for item in items),
        source_key=min(item.source_key for item in items),
        evidence_type=evidence_type,
        confidence=confidence,
        title=title,
        label=label,
        heading_level=heading_level,
        heading_confidence=heading_confidence,
        reading_order_confidence=min(item.reading_confidence for item in items),
        evidence_status=evidence_status,
        evidence=evidence,
    )


def _heading(text: str, maximum_characters: int) -> _Heading | None:
    stripped = " ".join(text.split())
    if not stripped or len(stripped) > maximum_characters or "\n" in text:
        return None
    appendix = _appendix_heading(stripped)
    if appendix is not None:
        return appendix
    normalized = _normalized_text(stripped)
    if normalized in _BIBLIOGRAPHY_TITLES:
        return _Heading(
            kind=StructureKind.BIBLIOGRAPHY,
            level=1,
            label=None,
            title=stripped,
            evidence_type="explicit_bibliography_heading",
            confidence=0.98,
        )
    numbered = _NUMBERED_HEADING.fullmatch(stripped)
    if numbered is not None:
        label = numbered.group("label")
        title = numbered.group("title").strip()
        level = label.count(".") + 1
        return _Heading(
            kind=(
                StructureKind.SECTION
                if level == 1
                else StructureKind.SUBSECTION
            ),
            level=level,
            label=label,
            title=title,
            evidence_type="numbered_heading",
            confidence=0.9,
        )
    if normalized in _KNOWN_SECTIONS:
        return _Heading(
            kind=StructureKind.SECTION,
            level=1,
            label=None,
            title=stripped,
            evidence_type="known_article_heading",
            confidence=0.75,
        )
    return None


def _appendix_heading(text: str) -> _Heading | None:
    match = _APPENDIX_HEADING.fullmatch(text)
    if match is None:
        return None
    label = match.group("label")
    title = (match.group("title") or "").strip()
    return _Heading(
        kind=StructureKind.APPENDIX,
        level=1,
        label=label,
        title=title or text.strip(),
        evidence_type="explicit_appendix_heading",
        confidence=0.95,
    )


def _front_kind(text: str) -> StructureKind | None:
    normalized = _normalized_text(text)
    if normalized == "abstract" or normalized.startswith("abstract:"):
        return StructureKind.ABSTRACT
    if normalized.startswith("keywords:") or normalized.startswith("keyword:"):
        return StructureKind.KEYWORDS
    return None


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


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())
