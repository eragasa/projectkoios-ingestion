"""Pure current-schema storage document-header record codec."""

from __future__ import annotations

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
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.input.document import (
    ReadingDocumentProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.lineage.definition import (  # noqa: E501
    ReadingEvidenceLineage,
)


class ReadingEvidenceStorageHeaderCodec:
    """Encode and reconstruct one canonical document-header payload."""

    __slots__ = ("json_contract",)

    def __init__(self) -> None:
        self.json_contract = ReadingEvidenceStorageJsonContract()

    def encode(self, document: ReadingEvidenceDocument) -> JsonValue:
        """Encode one exact canonical document-header payload."""
        lineage = document.lineage
        return {
            "producer_evidence": self.json_contract.to_json_value(
                document.producer_evidence
            ),
            "lineage": {
                "source_artifact": self.json_contract.to_json_value(
                    lineage.source_artifact
                ),
                "extraction_result_id": self.json_contract.to_json_value(
                    lineage.extraction_result_id
                ),
                "document_producer_id": self.json_contract.to_json_value(
                    lineage.document_producer_id
                ),
                "page_text_inventory_id": self.json_contract.to_json_value(
                    lineage.page_text_inventory_id
                ),
                "structured_item_inventory_id": (
                    self.json_contract.to_json_value(
                        lineage.structured_item_inventory_id
                    )
                ),
                "clean_text_inventory_id": self.json_contract.to_json_value(
                    lineage.clean_text_inventory_id
                ),
                "figure_inventory_id": self.json_contract.to_json_value(
                    lineage.figure_inventory_id
                ),
                "table_inventory_id": self.json_contract.to_json_value(
                    lineage.table_inventory_id
                ),
                "equation_inventory_id": self.json_contract.to_json_value(
                    lineage.equation_inventory_id
                ),
                "projection_configuration_id": self.json_contract.to_json_value(
                    lineage.projection_configuration_id
                ),
                "lineage_id": self.json_contract.to_json_value(
                    lineage.lineage_id
                ),
            },
            "contract_version": document.contract_version,
            "document_id": self.json_contract.to_json_value(
                document.document_id
            ),
        }

    def decode(
        self,
        value: JsonValue,
        references: ManagedArtifactReferenceInventory,
    ) -> tuple[
        ReadingDocumentProducerEvidence,
        ReadingEvidenceLineage,
        str,
        ReadingEvidenceIdentity,
    ]:
        """Reconstruct exact document header values and derived identities."""
        root = self._object(value, "document header")
        self._keys(
            root,
            {"producer_evidence", "lineage", "contract_version", "document_id"},
        )
        producer = self.json_contract.decode_as(
            root["producer_evidence"], ReadingDocumentProducerEvidence
        )
        raw = self._object(root["lineage"], "lineage")
        names = {
            "source_artifact",
            "extraction_result_id",
            "document_producer_id",
            "page_text_inventory_id",
            "structured_item_inventory_id",
            "clean_text_inventory_id",
            "figure_inventory_id",
            "table_inventory_id",
            "equation_inventory_id",
            "projection_configuration_id",
            "lineage_id",
        }
        self._keys(raw, names)
        lineage = ReadingEvidenceLineage(
            source_artifact=self.json_contract.decode_as(
                raw["source_artifact"], ManagedArtifactReference
            ),
            extraction_result_id=self._identity(raw["extraction_result_id"]),
            document_producer_id=self._identity(raw["document_producer_id"]),
            page_text_inventory_id=self._identity(
                raw["page_text_inventory_id"]
            ),
            structured_item_inventory_id=self._identity(
                raw["structured_item_inventory_id"]
            ),
            clean_text_inventory_id=self._identity(
                raw["clean_text_inventory_id"]
            ),
            figure_inventory_id=self._identity(raw["figure_inventory_id"]),
            table_inventory_id=self._identity(raw["table_inventory_id"]),
            equation_inventory_id=self._identity(raw["equation_inventory_id"]),
            projection_configuration_id=self._identity(
                raw["projection_configuration_id"]
            ),
            managed_artifacts=references,
        )
        if lineage.lineage_id != self._identity(raw["lineage_id"]):
            raise JsonParseError("stored lineage identity differs")
        return (
            producer,
            lineage,
            self._string(root["contract_version"], "contract_version"),
            self._identity(root["document_id"]),
        )

    def _identity(self, value: JsonValue) -> ReadingEvidenceIdentity:
        return self.json_contract.decode_as(value, ReadingEvidenceIdentity)

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
