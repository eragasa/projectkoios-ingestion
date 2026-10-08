"""Strict current-schema reading-evidence storage record reconstruction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.storage.transcript.reading.evidence.json.contract import (  # noqa: E501
    ReadingEvidenceStorageJsonContract,
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
from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
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
from projectkoios.ingestion.transcript.reading.evidence.input.equation.inventory import (  # noqa: E501
    ReadingEquationProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.evidence import (  # noqa: E501
    ReadingTableProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.definition import (  # noqa: E501
    ReadingEvidenceLimitation,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)

ReadingProducer = (
    ReadingCleanTextProducerEvidence
    | ReadingFigureProducerEvidence
    | ReadingTableProducerEvidence
    | ReadingEquationProducerEvidence
)
ReadingBlock = (
    ReadingTextEvidenceBlock
    | ReadingFigureEvidenceBlock
    | ReadingTableEvidenceBlock
    | ReadingEquationEvidenceBlock
)


class ReadingEvidenceStorageRecordGraphDecoder:
    """Reconstruct one canonical document from a complete child graph."""

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

    def decode(
        self, documents: ReadingEvidenceStorageDocumentInventory
    ) -> ReadingEvidenceDocument:
        """Reconstruct one canonical document from non-completion members."""
        if type(documents) is not ReadingEvidenceStorageDocumentInventory:
            raise TypeError("documents has an unsupported type")
        records = tuple(documents)
        if any(
            value.kind is ReadingEvidenceStorageRecordKind.COMPLETION
            for value in records
        ):
            raise JsonParseError("child record set contains completion member")
        headers = tuple(
            value
            for value in records
            if value.kind is ReadingEvidenceStorageRecordKind.DOCUMENT
        )
        if len(headers) != 1:
            raise JsonParseError("record set requires one document header")
        references = self._references(records)
        producer_map = self._decode_producers(records)
        blocks = tuple(
            self.block_codec.decode(record.payload(), producer_map)
            for record in records
            if record.kind is ReadingEvidenceStorageRecordKind.BLOCK
        )
        pages = self._decode_pages(records, blocks)
        limitations = self._limitations(records)
        figure_values = self._producers_of_type(
            producer_map, ReadingFigureProducerEvidence
        )
        table_values = self._producers_of_type(
            producer_map, ReadingTableProducerEvidence
        )
        equation_values = self._producers_of_type(
            producer_map, ReadingEquationProducerEvidence
        )
        producer, lineage, contract_version, stored_document_id = (
            self.header_codec.decode(headers[0].payload(), references)
        )
        document = ReadingEvidenceDocument(
            producer_evidence=producer,
            pages=ReadingEvidencePageInventory(*pages),
            retained_figures=ReadingFigureProducerEvidenceInventory(
                *cast(tuple[ReadingFigureProducerEvidence, ...], figure_values)
            ),
            retained_tables=ReadingTableProducerEvidenceInventory(
                *cast(tuple[ReadingTableProducerEvidence, ...], table_values)
            ),
            retained_equations=ReadingEquationProducerEvidenceInventory(
                *cast(
                    tuple[ReadingEquationProducerEvidence, ...], equation_values
                )
            ),
            managed_artifacts=references,
            lineage=lineage,
            limitations=limitations,
            contract_version=contract_version,
        )
        if document.document_id != stored_document_id:
            raise JsonParseError("stored document identity differs")
        if document.document_id.value != headers[0].semantic_id:
            raise JsonParseError("document semantic identity differs")
        clean_ids = {
            value.record_id.value
            for value in producer_map.values()
            if type(value) is ReadingCleanTextProducerEvidence
        }
        used_clean_ids = {
            source.record_id.value
            for page in document.pages
            for block in page.blocks
            if type(block) is ReadingTextEvidenceBlock
            for source in block.sources
        }
        if clean_ids != used_clean_ids:
            raise JsonParseError("clean producer membership is not exact")
        return document

    def _references(
        self, records: tuple[ReadingEvidenceStorageDocument, ...]
    ) -> ManagedArtifactReferenceInventory:
        values = tuple(
            self._decode_semantic(record, ManagedArtifactReference)
            for record in records
            if record.kind is ReadingEvidenceStorageRecordKind.MANAGED_REFERENCE
        )
        return ManagedArtifactReferenceInventory(
            *sorted(values, key=lambda value: value.artifact_id)
        )

    def _limitations(
        self, records: tuple[ReadingEvidenceStorageDocument, ...]
    ) -> ReadingEvidenceLimitationInventory:
        values = tuple(
            self._decode_semantic(record, ReadingEvidenceLimitation)
            for record in records
            if record.kind is ReadingEvidenceStorageRecordKind.LIMITATION
        )
        return ReadingEvidenceLimitationInventory(
            *sorted(values, key=lambda value: value.limitation_id.value)
        )

    def _decode_producers(
        self, records: tuple[ReadingEvidenceStorageDocument, ...]
    ) -> dict[str, ReadingProducer]:
        result: dict[str, ReadingProducer] = {}
        for record in records:
            expected = self.PRODUCER_TYPES.get(record.kind)
            if expected is None:
                continue
            producer = cast(
                ReadingProducer,
                self.json_contract.decode_as(record.payload(), expected),
            )
            if producer.record_id.value != record.semantic_id:
                raise JsonParseError("producer semantic identity differs")
            if record.semantic_id in result:
                raise JsonParseError("producer semantic identity is duplicated")
            result[record.semantic_id] = producer
        return result

    def _decode_pages(
        self,
        records: tuple[ReadingEvidenceStorageDocument, ...],
        blocks: tuple[ReadingBlock, ...],
    ) -> tuple[ReadingEvidencePage, ...]:
        pages: list[ReadingEvidencePage] = []
        used_blocks: set[str] = set()
        for record in records:
            if record.kind is not ReadingEvidenceStorageRecordKind.PAGE:
                continue
            payload = self._object(record.payload(), "page")
            self._keys(payload, {"page_text", "page_id"})
            page_text = self.json_contract.decode_as(
                payload["page_text"], ReadingPageTextProducerEvidence
            )
            page_blocks = sorted(
                (
                    block
                    for block in blocks
                    if block.structured_item.page_location
                    == page_text.selection.page_location
                ),
                key=lambda block: block.structured_item.order_index,
            )
            page = ReadingEvidencePage(
                page_text=page_text,
                blocks=ReadingEvidenceBlockInventory(*page_blocks),
            )
            if page.page_id != self.json_contract.decode_as(
                payload["page_id"],
                type(page.page_id),
            ):
                raise JsonParseError("stored page identity differs")
            if page.page_id.value != record.semantic_id:
                raise JsonParseError("page semantic identity differs")
            pages.append(page)
            used_blocks.update(value.block_id.value for value in page_blocks)
        if used_blocks != {value.block_id.value for value in blocks}:
            raise JsonParseError("block membership is not exact")
        pages.sort(
            key=lambda value: (
                value.page_text.selection.page_location.physical_page_index
            )
        )
        return tuple(pages)

    def _decode_semantic[SemanticT](
        self,
        record: ReadingEvidenceStorageDocument,
        expected: type[SemanticT],
    ) -> SemanticT:
        value = self.json_contract.decode_as(record.payload(), expected)
        semantic_id = getattr(value, "artifact_id", None) or getattr(
            getattr(value, "limitation_id", None), "value", None
        )
        if semantic_id != record.semantic_id:
            raise JsonParseError("record semantic identity differs")
        return value

    @staticmethod
    def _producers_of_type(
        values: Mapping[str, ReadingProducer], expected: type[object]
    ) -> tuple[ReadingProducer, ...]:
        return tuple(
            sorted(
                (value for value in values.values() if type(value) is expected),
                key=lambda value: value.record_id.value,
            )
        )

    @staticmethod
    def _object(value: JsonValue, name: str) -> dict[str, JsonValue]:
        if type(value) is not dict:
            raise JsonParseError(f"{name} must be an object")
        return value

    @staticmethod
    def _keys(value: dict[str, JsonValue], expected: set[str]) -> None:
        if set(value) != expected:
            raise JsonParseError("record fields differ from current schema")
