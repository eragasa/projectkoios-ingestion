"""Article-structure proposal section."""

from __future__ import annotations

import re

from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.evidence.text import (
    _TextEvidence,
)
from projectkoios.ingestion.articles.structure.heading.analysis import (
    _appendix_heading,
    _heading,
)
from projectkoios.ingestion.articles.structure.limits.error import (
    ArticleStructureLimitError,
)
from projectkoios.ingestion.articles.structure.proposal.factory import (
    _proposal_from_evidence,
)
from projectkoios.ingestion.articles.structure.proposal.model import (
    _Proposal,
    _WarningProposal,
)
from projectkoios.ingestion.structure import (
    StructureEvidenceStatus,
    StructureKind,
)

_BIBLIOGRAPHY_ENTRY = re.compile(
    r"^\s*(?:\[\d+\]|\d+[.)]\s+|[A-Z][^\n]{0,100}\(\d{4}[a-z]?\))"
)


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
