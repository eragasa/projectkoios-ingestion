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
from projectkoios.ingestion.transcription.evidence_status import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.item_kind import TranscriptionItemKind


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
        item_kind = cls.item_kind_for(node.kind)
        evidence_status = (
            TranscriptionEvidenceStatus.AMBIGUOUS
            if node.evidence_status is StructureEvidenceStatus.UNCERTAIN
            else TranscriptionEvidenceStatus.PROPOSED
        )
        return cls(node.node_id, item_kind, evidence_status)

    @classmethod
    def item_kind_for(
        cls, structure_kind: StructureKind
    ) -> TranscriptionItemKind | None:
        if structure_kind in (
            StructureKind.TITLE,
            StructureKind.PART,
            StructureKind.CHAPTER,
            StructureKind.SECTION,
            StructureKind.SUBSECTION,
            StructureKind.APPENDIX,
        ):
            item_kind = TranscriptionItemKind.HEADING
        elif structure_kind is StructureKind.EQUATION:
            item_kind = TranscriptionItemKind.EQUATION
        elif structure_kind is StructureKind.TABLE:
            item_kind = TranscriptionItemKind.TABLE
        elif structure_kind is StructureKind.FIGURE:
            item_kind = TranscriptionItemKind.FIGURE
        elif structure_kind in (
            StructureKind.DOCUMENT,
            StructureKind.FRONT_MATTER,
            StructureKind.PROBLEM_SET,
            StructureKind.BIBLIOGRAPHY,
            StructureKind.INDEX,
        ):
            item_kind = None
        else:
            item_kind = TranscriptionItemKind.PROSE
        return item_kind

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
