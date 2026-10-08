"""Pure observational inventories for canonical reading evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.association.evidence import (  # noqa: E501
    ReadingAssociationEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.measures import (  # noqa: E501
    ReadingEvidenceInventoryMeasures,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceInventory:
    """Carry an independently recomputed canonical document inventory."""

    measures: ReadingEvidenceInventoryMeasures
    inventory_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.measures) is not ReadingEvidenceInventoryMeasures:
            raise TypeError("measures must be ReadingEvidenceInventoryMeasures")
        object.__setattr__(
            self,
            "inventory_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.EVIDENCE_INVENTORY,
                prefix="observed-reading-evidence-inventory",
                material={"measures_id": self.measures.measures_id.value},
            ),
        )

    @classmethod
    def observe(
        cls, document: ReadingEvidenceDocument
    ) -> ReadingEvidenceInventory:
        """Recompute exact counts and digests from one canonical document."""
        if type(document) is not ReadingEvidenceDocument:
            raise TypeError("document must be ReadingEvidenceDocument")
        pages = tuple(document.pages)
        blocks = tuple(block for page in pages for block in page.blocks)
        streams = tuple(
            stream for page in pages for stream in page.page_text.streams
        )
        text_blocks = tuple(
            block for block in blocks if type(block) is ReadingTextEvidenceBlock
        )
        figure_blocks = tuple(
            block
            for block in blocks
            if type(block) is ReadingFigureEvidenceBlock
        )
        association_values: list[ReadingAssociationEvidence] = []
        for figure_producer in document.retained_figures:
            association_values.extend(figure_producer.assessment.associations)
        for table_producer in document.retained_tables:
            association_values.extend(table_producer.assessment.associations)
        associations = tuple(association_values)
        equations = tuple(document.retained_equations)
        text_values = (
            *(stream.text for stream in streams),
            *(block.text for block in text_blocks),
            *(association.text for association in associations),
            *(
                value
                for producer in equations
                for value in (
                    producer.native_representation,
                    producer.recognized_representation,
                )
                if value is not None
            ),
        )
        producer_ids = (
            document.producer_evidence.record_id.value,
            document.lineage.page_text_inventory_id.value,
            document.lineage.structured_item_inventory_id.value,
            document.lineage.clean_text_inventory_id.value,
            document.lineage.figure_inventory_id.value,
            document.lineage.table_inventory_id.value,
            document.lineage.equation_inventory_id.value,
        )
        measures = ReadingEvidenceInventoryMeasures(
            page_count=len(pages),
            stream_count=len(streams),
            selection_count=len(pages),
            block_count=len(blocks),
            paragraph_count=sum(
                block.kind is ReadingEvidenceBlockKind.PARAGRAPH
                for block in blocks
            ),
            heading_count=sum(
                block.kind is ReadingEvidenceBlockKind.HEADING
                for block in blocks
            ),
            figure_count=len(document.retained_figures),
            table_count=len(document.retained_tables),
            equation_count=len(equations),
            caption_count=sum(
                block.caption is not None for block in figure_blocks
            ),
            gate_count=len(equations),
            association_count=len(associations),
            artifact_count=len(document.managed_artifacts),
            character_count=sum(len(value) for value in text_values),
            utf8_byte_count=sum(len(value.encode()) for value in text_values),
            limitation_count=len(document.limitations),
            pages_sha256=cls.digest_identity_material(
                document.pages.identity_material()
            ),
            blocks_sha256=cls.digest_identity_material(
                [block.block_id.value for block in blocks]
            ),
            producers_sha256=cls.digest_identity_material(producer_ids),
            artifacts_sha256=cls.digest_identity_material(
                [value.artifact_id for value in document.managed_artifacts]
            ),
            limitations_sha256=cls.digest_identity_material(
                document.limitations.identity_material()
            ),
            lineage_id=document.lineage.lineage_id,
        )
        return cls(measures=measures)

    @classmethod
    def digest_identity_material(cls, identities: object) -> SHA256Hash:
        """Fingerprint one bounded canonical semantic identity collection."""
        return SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_bytes(identities)
        )
