"""Article-structure proposal front."""

from __future__ import annotations

import re

from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.evidence.text import (
    _TextEvidence,
)
from projectkoios.ingestion.articles.structure.heading.analysis import _heading
from projectkoios.ingestion.articles.structure.normalization.text import (
    _normalized_text,
)
from projectkoios.ingestion.articles.structure.proposal.factory import (
    _proposal_from_evidence,
)
from projectkoios.ingestion.articles.structure.proposal.model import (
    _Proposal,
    _WarningProposal,
)
from projectkoios.ingestion.models import (
    ExtractedDocument,
)
from projectkoios.ingestion.structure import (
    StructureEvidenceStatus,
    StructureKind,
)

_AUTHOR_LINE = re.compile(
    r"^\s*(?:by|authors?)\s*[:\-]?\s*(?P<names>\S.*)$",
    re.IGNORECASE,
)


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


def _front_kind(text: str) -> StructureKind | None:
    normalized = _normalized_text(text)
    if normalized == "abstract" or normalized.startswith("abstract:"):
        return StructureKind.ABSTRACT
    if normalized.startswith("keywords:") or normalized.startswith("keyword:"):
        return StructureKind.KEYWORDS
    return None
