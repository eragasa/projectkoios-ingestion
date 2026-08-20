from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    IngestionWarning,
    Metadata,
    SourceSpan,
)


class StructureKind(StrEnum):
    DOCUMENT = "document"
    FRONT_MATTER = "front_matter"
    PART = "part"
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    PROSE = "prose"
    EQUATION = "equation"
    FIGURE = "figure"
    TABLE = "table"
    EXAMPLE = "example"
    PROBLEM_SET = "problem_set"
    PROBLEM = "problem"
    APPENDIX = "appendix"
    BIBLIOGRAPHY = "bibliography"
    INDEX = "index"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StructureNode:
    node_id: str
    kind: StructureKind
    source_spans: tuple[SourceSpan, ...]
    evidence_type: str
    confidence: float
    label: str | None = None
    title: str | None = None
    parent_id: str | None = None
    child_ids: tuple[str, ...] = ()
    evidence: Metadata = ()
    warning_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: StructureKind,
        source_spans: tuple[SourceSpan, ...],
        evidence_type: str,
        confidence: float,
        label: str | None = None,
        title: str | None = None,
        parent_id: str | None = None,
        child_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
        warning_ids: tuple[str, ...] = (),
    ) -> StructureNode:
        node_id = stable_id(
            "structure",
            kind,
            tuple(span.identity_parts() for span in source_spans),
            label,
        )
        return cls(
            node_id=node_id,
            kind=kind,
            source_spans=source_spans,
            evidence_type=evidence_type,
            confidence=confidence,
            label=label,
            title=title,
            parent_id=parent_id,
            child_ids=child_ids,
            evidence=evidence,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        if not self.source_spans:
            raise ValueError("a structure node must have source spans")
        if not self.evidence_type:
            raise ValueError("evidence_type must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.parent_id == self.node_id:
            raise ValueError("a structure node cannot be its own parent")
        if self.node_id in self.child_ids:
            raise ValueError("a structure node cannot be its own child")
        if len(self.child_ids) != len(set(self.child_ids)):
            raise ValueError("child IDs must be unique")


@dataclass(frozen=True)
class StructureAnalysis:
    nodes: tuple[StructureNode, ...]
    warnings: tuple[IngestionWarning, ...] = ()

    def __post_init__(self) -> None:
        nodes_by_id = {node.node_id: node for node in self.nodes}
        if len(nodes_by_id) != len(self.nodes):
            raise ValueError("structure node IDs must be unique")

        for node in self.nodes:
            if node.parent_id is not None:
                if node.parent_id not in nodes_by_id:
                    raise ValueError(
                        "structure parent must exist in the analysis"
                    )
                parent = nodes_by_id[node.parent_id]
                if node.node_id not in parent.child_ids:
                    raise ValueError(
                        "parent and child relationships must be reciprocal"
                    )

            for child_id in node.child_ids:
                if child_id not in nodes_by_id:
                    raise ValueError(
                        "structure child must exist in the analysis"
                    )
                if nodes_by_id[child_id].parent_id != node.node_id:
                    raise ValueError(
                        "parent and child relationships must be reciprocal"
                    )

            seen: set[str] = set()
            current = node
            while current.parent_id is not None:
                if current.node_id in seen:
                    raise ValueError(
                        "structure hierarchy cannot contain cycles"
                    )
                seen.add(current.node_id)
                current = nodes_by_id[current.parent_id]

        warning_ids = {warning.warning_id for warning in self.warnings}
        for node in self.nodes:
            if not set(node.warning_ids).issubset(warning_ids):
                raise ValueError(
                    "structure warning IDs must refer to analysis warnings"
                )
