"""Pure current-schema storage block record codec."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.storage.transcript.reading.evidence.json.contract import (  # noqa: E501
    ReadingEvidenceStorageJsonContract,
)
from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.basis import (  # noqa: E501
    ReadingTextBlockProjectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.source import (  # noqa: E501
    ReadingTextBlockSourceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.evidence import (  # noqa: E501
    ReadingEquationProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
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
ReadingBlock = (
    ReadingTextEvidenceBlock
    | ReadingFigureEvidenceBlock
    | ReadingTableEvidenceBlock
    | ReadingEquationEvidenceBlock
)


class ReadingEvidenceStorageBlockCodec:
    """Encode and reconstruct one canonical block record payload."""

    __slots__ = ("json_contract",)

    def __init__(self) -> None:
        self.json_contract = ReadingEvidenceStorageJsonContract()

    def encode(self, block: ReadingBlock) -> JsonValue:
        """Encode one exact canonical block payload."""
        if type(block) is ReadingTextEvidenceBlock:
            detail: JsonValue = {
                "source_record_ids": [
                    value.record_id.value for value in block.sources
                ],
                "basis": self.json_contract.to_json_value(block.basis),
            }
        elif type(block) is ReadingFigureEvidenceBlock:
            detail = {
                "producer_record_id": block.producer_evidence.record_id.value,
                "caption": self.json_contract.to_json_value(block.caption),
            }
        elif type(block) is ReadingTableEvidenceBlock:
            detail = {
                "producer_record_id": block.producer_evidence.record_id.value
            }
        elif type(block) is ReadingEquationEvidenceBlock:
            detail = {
                "producer_record_id": block.producer_evidence.record_id.value
            }
        else:
            raise TypeError("block has an unsupported type")
        return {
            "kind": self.json_contract.to_json_value(block.kind),
            "structured_item": self.json_contract.to_json_value(
                block.structured_item
            ),
            "detail": detail,
            "block_id": self.json_contract.to_json_value(block.block_id),
        }

    def decode(
        self,
        value: JsonValue,
        producers: Mapping[str, ReadingProducer],
    ) -> ReadingBlock:
        """Reconstruct one exact canonical block from record payload."""
        root = self._object(value, "block")
        self._keys(root, {"kind", "structured_item", "detail", "block_id"})
        kind = self.json_contract.decode_as(
            root["kind"], ReadingEvidenceBlockKind
        )
        structured = self.json_contract.decode_as(
            root["structured_item"], ReadingStructuredItemProducerEvidence
        )
        detail = self._object(root["detail"], "block detail")
        if kind in (
            ReadingEvidenceBlockKind.PARAGRAPH,
            ReadingEvidenceBlockKind.HEADING,
        ):
            self._keys(detail, {"source_record_ids", "basis"})
            source_ids = detail["source_record_ids"]
            if type(source_ids) is not list or any(
                type(item) is not str for item in source_ids
            ):
                raise JsonParseError("text source identities are invalid")
            sources: list[ReadingCleanTextProducerEvidence] = []
            for source_id in source_ids:
                producer = self._producer(producers, cast(str, source_id))
                if type(producer) is not ReadingCleanTextProducerEvidence:
                    raise JsonParseError("text block references wrong producer")
                sources.append(producer)
            block: ReadingBlock = ReadingTextEvidenceBlock(
                structured_item=structured,
                sources=ReadingTextBlockSourceInventory(*sources),
                basis=self.json_contract.decode_as(
                    detail["basis"], ReadingTextBlockProjectionBasis
                ),
            )
        elif kind is ReadingEvidenceBlockKind.FIGURE:
            self._keys(detail, {"producer_record_id", "caption"})
            producer = self._producer(
                producers,
                self._string(detail["producer_record_id"], "producer"),
            )
            if type(producer) is not ReadingFigureProducerEvidence:
                raise JsonParseError("figure block references wrong producer")
            caption_value = detail["caption"]
            caption = (
                None
                if caption_value is None
                else self.json_contract.decode_as(
                    caption_value, ReadingCaptionEvidence
                )
            )
            block = ReadingFigureEvidenceBlock(
                structured_item=structured,
                producer_evidence=producer,
                caption=caption,
            )
        elif kind is ReadingEvidenceBlockKind.TABLE:
            self._keys(detail, {"producer_record_id"})
            producer = self._producer(
                producers,
                self._string(detail["producer_record_id"], "producer"),
            )
            if type(producer) is not ReadingTableProducerEvidence:
                raise JsonParseError("table block references wrong producer")
            block = ReadingTableEvidenceBlock(
                structured_item=structured,
                producer_evidence=producer,
            )
        elif kind is ReadingEvidenceBlockKind.EQUATION:
            self._keys(detail, {"producer_record_id"})
            producer = self._producer(
                producers,
                self._string(detail["producer_record_id"], "producer"),
            )
            if type(producer) is not ReadingEquationProducerEvidence:
                raise JsonParseError("equation block references wrong producer")
            block = ReadingEquationEvidenceBlock(
                structured_item=structured,
                producer_evidence=producer,
            )
        else:
            raise JsonParseError("block kind is unsupported")
        if block.block_id != self.json_contract.decode_as(
            root["block_id"], ReadingEvidenceIdentity
        ):
            raise JsonParseError("stored block identity differs")
        return block

    @staticmethod
    def _producer(
        values: Mapping[str, ReadingProducer], semantic_id: str
    ) -> ReadingProducer:
        try:
            return values[semantic_id]
        except KeyError as error:
            raise JsonParseError("block references missing producer") from error

    @staticmethod
    def _object(value: JsonValue, name: str) -> dict[str, JsonValue]:
        if type(value) is not dict:
            raise JsonParseError(f"{name} must be an object")
        return value

    @staticmethod
    def _string(value: JsonValue, name: str) -> str:
        if type(value) is not str:
            raise JsonParseError(f"{name} must be a string")
        return value

    @staticmethod
    def _keys(value: dict[str, JsonValue], expected: set[str]) -> None:
        if set(value) != expected:
            raise JsonParseError("record fields differ from current schema")
