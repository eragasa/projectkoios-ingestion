"""Pure canonical reading-evidence storage record-graph encoding."""

from __future__ import annotations

from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.storage.transcript.reading.evidence.json.contract import (  # noqa: E501
    ReadingEvidenceStorageJsonContract,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceStorageProjectionConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.document import (  # noqa: E501
    ReadingEvidenceStorageDocument,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.inventory import (  # noqa: E501
    ReadingEvidenceStorageDocumentInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.kind import (  # noqa: E501
    ReadingEvidenceStorageRecordKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.record.block.codec import (  # noqa: E501
    ReadingEvidenceStorageBlockCodec,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.record.header.codec import (  # noqa: E501
    ReadingEvidenceStorageHeaderCodec,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.evidence import (  # noqa: E501
    ReadingEquationProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.evidence import (  # noqa: E501
    ReadingTableProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)

ReadingProducer = (
    ReadingCleanTextProducerEvidence
    | ReadingFigureProducerEvidence
    | ReadingTableProducerEvidence
    | ReadingEquationProducerEvidence
)


class ReadingEvidenceStorageRecordGraphEncoder:
    """Decompose one canonical document into non-completion records."""

    __slots__ = ("block_codec", "header_codec", "json_contract")

    PRODUCER_TYPES = {
        ReadingEvidenceStorageRecordKind.CLEAN_TEXT_PRODUCER: (
            ReadingCleanTextProducerEvidence
        ),
        ReadingEvidenceStorageRecordKind.FIGURE_PRODUCER: (
            ReadingFigureProducerEvidence
        ),
        ReadingEvidenceStorageRecordKind.TABLE_PRODUCER: (
            ReadingTableProducerEvidence
        ),
        ReadingEvidenceStorageRecordKind.EQUATION_PRODUCER: (
            ReadingEquationProducerEvidence
        ),
    }

    def __init__(self) -> None:
        self.json_contract = ReadingEvidenceStorageJsonContract()
        self.block_codec = ReadingEvidenceStorageBlockCodec()
        self.header_codec = ReadingEvidenceStorageHeaderCodec()

    def encode(
        self,
        *,
        document: ReadingEvidenceDocument,
        configuration: ReadingEvidenceStorageProjectionConfiguration,
    ) -> ReadingEvidenceStorageDocumentInventory:
        """Encode every non-completion member of one canonical document."""
        if type(document) is not ReadingEvidenceDocument:
            raise TypeError("document has an unsupported type")
        if (
            type(configuration)
            is not ReadingEvidenceStorageProjectionConfiguration
        ):
            raise TypeError("configuration has an unsupported type")
        records: list[ReadingEvidenceStorageDocument] = [
            self._record(
                document=document,
                configuration=configuration,
                kind=ReadingEvidenceStorageRecordKind.DOCUMENT,
                semantic_id=document.document_id.value,
                payload=self.header_codec.encode(document),
            )
        ]
        producers: dict[str, ReadingProducer] = {}
        for page in document.pages:
            records.append(
                self._record(
                    document=document,
                    configuration=configuration,
                    kind=ReadingEvidenceStorageRecordKind.PAGE,
                    semantic_id=page.page_id.value,
                    payload={
                        "page_text": self.json_contract.to_json_value(
                            page.page_text
                        ),
                        "page_id": self.json_contract.to_json_value(
                            page.page_id
                        ),
                    },
                )
            )
            for block in page.blocks:
                records.append(
                    self._record(
                        document=document,
                        configuration=configuration,
                        kind=ReadingEvidenceStorageRecordKind.BLOCK,
                        semantic_id=block.block_id.value,
                        payload=self.block_codec.encode(block),
                    )
                )
                if type(block) is ReadingTextEvidenceBlock:
                    for clean_producer in block.sources:
                        self._retain_producer(producers, clean_producer)
        for retained_producer in (
            *document.retained_figures,
            *document.retained_tables,
            *document.retained_equations,
        ):
            self._retain_producer(producers, retained_producer)
        for semantic_id in sorted(producers):
            producer = producers[semantic_id]
            records.append(
                self._record(
                    document=document,
                    configuration=configuration,
                    kind=self._producer_kind(producer),
                    semantic_id=semantic_id,
                    payload=self.json_contract.to_json_value(producer),
                )
            )
        for reference in document.managed_artifacts:
            records.append(
                self._record(
                    document=document,
                    configuration=configuration,
                    kind=ReadingEvidenceStorageRecordKind.MANAGED_REFERENCE,
                    semantic_id=reference.artifact_id,
                    payload=self.json_contract.to_json_value(reference),
                )
            )
        for limitation in document.limitations:
            records.append(
                self._record(
                    document=document,
                    configuration=configuration,
                    kind=ReadingEvidenceStorageRecordKind.LIMITATION,
                    semantic_id=limitation.limitation_id.value,
                    payload=self.json_contract.to_json_value(limitation),
                )
            )
        if len(records) > configuration.maximum_record_count:
            raise ValueError(
                "storage projection record count exceeds its limit"
            )
        records.sort(
            key=lambda value: (value.kind.collection.value, value.document_id)
        )
        return ReadingEvidenceStorageDocumentInventory(*records)

    def _record(
        self,
        *,
        document: ReadingEvidenceDocument,
        configuration: ReadingEvidenceStorageProjectionConfiguration,
        kind: ReadingEvidenceStorageRecordKind,
        semantic_id: str,
        payload: JsonValue,
    ) -> ReadingEvidenceStorageDocument:
        return ReadingEvidenceStorageDocument.create(
            schema_version=configuration.schema_version,
            generation_id=configuration.generation_id,
            evidence_document_id=document.document_id,
            kind=kind,
            semantic_id=semantic_id,
            payload=payload,
            maximum_document_bytes=configuration.maximum_document_bytes,
        )

    @classmethod
    def _producer_kind(
        cls, producer: ReadingProducer
    ) -> ReadingEvidenceStorageRecordKind:
        for kind, expected in cls.PRODUCER_TYPES.items():
            if type(producer) is expected:
                return kind
        raise TypeError("producer has an unsupported type")

    @staticmethod
    def _retain_producer(
        values: dict[str, ReadingProducer], producer: ReadingProducer
    ) -> None:
        existing = values.get(producer.record_id.value)
        if existing is not None and existing != producer:
            raise ValueError("producer identity has conflicting evidence")
        values[producer.record_id.value] = producer
