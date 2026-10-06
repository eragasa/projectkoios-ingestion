"""Article-structure proposal order."""

from __future__ import annotations

from projectkoios.ingestion.articles.structure.normalization.text import (
    _normalized_text,
)
from projectkoios.ingestion.articles.structure.proposal.model import _Proposal
from projectkoios.ingestion.models import (
    TableOfContentsEntry,
)
from projectkoios.ingestion.structure import (
    StructureKind,
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
