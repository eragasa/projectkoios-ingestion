"""Pure current-schema canonical document and storage-record graph codec."""

from __future__ import annotations

from projectkoios.ingestion.storage.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceStorageProjectionConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.inventory import (  # noqa: E501
    ReadingEvidenceStorageDocumentInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.record.graph.decoder import (  # noqa: E501
    ReadingEvidenceStorageRecordGraphDecoder,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.record.graph.encoder import (  # noqa: E501
    ReadingEvidenceStorageRecordGraphEncoder,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)


class ReadingEvidenceStorageRecordCodec:
    """Compose current record-graph encoding and strict reconstruction."""

    __slots__ = ("decoder", "encoder")

    def __init__(self) -> None:
        self.encoder = ReadingEvidenceStorageRecordGraphEncoder()
        self.decoder = ReadingEvidenceStorageRecordGraphDecoder()

    def encode_children(
        self,
        *,
        document: ReadingEvidenceDocument,
        configuration: ReadingEvidenceStorageProjectionConfiguration,
    ) -> ReadingEvidenceStorageDocumentInventory:
        """Encode every non-completion member of one canonical document."""
        return self.encoder.encode(
            document=document,
            configuration=configuration,
        )

    def decode_children(
        self, documents: ReadingEvidenceStorageDocumentInventory
    ) -> ReadingEvidenceDocument:
        """Reconstruct one canonical document from non-completion members."""
        return self.decoder.decode(documents)
