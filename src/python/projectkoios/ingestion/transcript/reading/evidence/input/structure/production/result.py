"""Immutable current structured-item production results."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.inventory import (  # noqa: E501
    ReadingStructuredItemProducerEvidenceInventory,
)


@dataclass(frozen=True, slots=True)
class ReadingStructuredItemProductionResult(AbstractDataObjectActionResult):
    """Bind exact current transcription lineage to structured evidence."""

    source_result_id: ReadingEvidenceIdentity
    page_text_ids: ReadingEvidenceIdentityInventory
    evidence: ReadingStructuredItemProducerEvidenceInventory
    result_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.source_result_id) is not ReadingEvidenceIdentity or (
            self.source_result_id.kind
            is not ReadingEvidenceIdentityKind.STRUCTURED_TRANSCRIPTION
        ):
            raise TypeError(
                "source_result_id must be a structured-transcription identity"
            )
        if type(self.page_text_ids) is not ReadingEvidenceIdentityInventory or (
            self.page_text_ids.kind is not ReadingEvidenceIdentityKind.PAGE_TEXT
        ):
            raise TypeError(
                "page_text_ids must be a page-text identity inventory"
            )
        if (
            type(self.evidence)
            is not ReadingStructuredItemProducerEvidenceInventory
        ):
            raise TypeError(
                "evidence must be a structured-item producer inventory"
            )
        page_text_material = self.page_text_ids.identity_material()
        evidence_material = self.evidence.identity_material()
        page_text_digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_bytes(page_text_material)
        )
        evidence_digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_bytes(evidence_material)
        )
        object.__setattr__(
            self,
            "result_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.STRUCTURED_ITEM_PRODUCTION,
                prefix="reading-structured-item-production",
                material={
                    "source_result_id": self.source_result_id.value,
                    "page_text_count": len(page_text_material),
                    "page_text_ids_sha256": page_text_digest,
                    "structured_item_count": len(evidence_material),
                    "structured_item_ids_sha256": evidence_digest,
                },
            ),
        )
