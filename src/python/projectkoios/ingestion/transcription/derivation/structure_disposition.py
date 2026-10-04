from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.structure import (
    StructureEvidenceStatus,
    StructureKind,
    StructureNode,
)
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.evidence.status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item.kind import TranscriptionItemKind


@dataclass(frozen=True)
class TranscriptionStructureDisposition(
    AbstractDerivation, AbstractTranscriptionDataObject
):
    node_id: str
    item_kind: TranscriptionItemKind | None
    evidence_status: TranscriptionEvidenceStatus
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def derive(cls, node: StructureNode) -> TranscriptionStructureDisposition:
        if node.kind in (
            StructureKind.TITLE,
            StructureKind.PART,
            StructureKind.CHAPTER,
            StructureKind.SECTION,
            StructureKind.SUBSECTION,
            StructureKind.APPENDIX,
        ):
            item_kind = TranscriptionItemKind.HEADING
        elif node.kind is StructureKind.EQUATION:
            item_kind = TranscriptionItemKind.EQUATION
        elif node.kind is StructureKind.TABLE:
            item_kind = TranscriptionItemKind.TABLE
        elif node.kind is StructureKind.FIGURE:
            item_kind = TranscriptionItemKind.FIGURE
        elif node.kind in (
            StructureKind.DOCUMENT,
            StructureKind.FRONT_MATTER,
            StructureKind.PROBLEM_SET,
            StructureKind.BIBLIOGRAPHY,
            StructureKind.INDEX,
        ):
            item_kind = None
        else:
            item_kind = TranscriptionItemKind.PROSE
        evidence_status = (
            TranscriptionEvidenceStatus.AMBIGUOUS
            if node.evidence_status is StructureEvidenceStatus.UNCERTAIN
            else TranscriptionEvidenceStatus.PROPOSED
        )
        return cls(node.node_id, item_kind, evidence_status)

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported structure disposition version")
        self.validate_identity_fields(self.node_id)
        if self.item_kind is not None and not isinstance(
            self.item_kind, TranscriptionItemKind
        ):
            raise TypeError("structure disposition item kind is unsupported")
        if not isinstance(self.evidence_status, TranscriptionEvidenceStatus):
            raise TypeError(
                "structure disposition evidence status is unsupported"
            )
