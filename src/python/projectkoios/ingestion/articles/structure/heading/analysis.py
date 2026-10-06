"""Article-structure heading analysis."""

from __future__ import annotations

import re

from projectkoios.ingestion.articles.structure.heading.model import _Heading
from projectkoios.ingestion.articles.structure.normalization.text import (
    _normalized_text,
)
from projectkoios.ingestion.structure import (
    StructureKind,
)

_NUMBERED_HEADING = re.compile(
    r"^\s*(?P<label>\d+(?:\.\d+)*)(?:[.)])?\s+(?P<title>\S.*)\s*$"
)


_APPENDIX_HEADING = re.compile(
    r"^\s*appendix(?:\s+(?P<label>[A-Za-z0-9]+))?"
    r"(?:\s*[:.\-]?\s*(?P<title>.*))?$",
    re.IGNORECASE,
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
