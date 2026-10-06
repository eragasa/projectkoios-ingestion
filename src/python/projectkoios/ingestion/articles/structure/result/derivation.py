"""Article-structure result derivation."""

from __future__ import annotations

from dataclasses import replace

from projectkoios.ingestion.articles.structure.proposal.model import (
    _Proposal,
    _WarningProposal,
)
from projectkoios.ingestion.models import (
    IngestionWarning,
    WarningSeverity,
)
from projectkoios.ingestion.structure import (
    StructureNode,
)


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
