"""Article-structure proposal derivation."""

from __future__ import annotations

from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.evidence.span import (
    _ordered_unique_spans,
)
from projectkoios.ingestion.articles.structure.evidence.text import (
    _TextEvidence,
)
from projectkoios.ingestion.articles.structure.limits.error import (
    ArticleStructureLimitError,
)
from projectkoios.ingestion.articles.structure.proposal.front import (
    _abstract_proposal,
    _author_proposal,
    _keywords_proposal,
    _title_proposal,
)
from projectkoios.ingestion.articles.structure.proposal.model import (
    _Proposal,
    _WarningProposal,
)
from projectkoios.ingestion.articles.structure.proposal.order import (
    _apply_table_of_contents,
    _assign_section_parents,
)
from projectkoios.ingestion.articles.structure.proposal.section import (
    _section_proposals,
)
from projectkoios.ingestion.layout import (
    PageLayoutResult,
)
from projectkoios.ingestion.models import (
    ExtractedDocument,
)
from projectkoios.ingestion.structure import (
    StructureEvidenceStatus,
    StructureKind,
)


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
