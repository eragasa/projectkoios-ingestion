"""Canonical JSON codec for safe publication authority receipts."""

from __future__ import annotations

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.page.projection.publication.code import (
    PageProjectionPublicationCodeInventory,
)
from projectkoios.ingestion.page.projection.publication.receipt import (
    PageProjectionPublicationReceipt,
)
from projectkoios.ingestion.sha256.hash import SHA256Hash

_RECEIPT_FIELDS = frozenset(
    {
        "artifact_verification_result_id",
        "block_count",
        "contract_name",
        "contract_version",
        "enrichment_available_count",
        "enrichment_inventory_id",
        "enrichment_result_id",
        "enrichment_unavailable_count",
        "extracted_document_id",
        "extraction_manifest_id",
        "extraction_warning_codes",
        "extraction_warning_count",
        "page_count",
        "page_projection_inventory_id",
        "page_projection_limitation_codes",
        "page_projection_limitation_count",
        "page_projection_result_id",
        "payload_byte_length",
        "payload_id",
        "payload_sha256",
        "pipeline_configuration_id",
        "publication_id",
        "reading_document_id",
        "reading_inventory_id",
        "reading_limitation_codes",
        "reading_limitation_count",
        "reading_projection_result_id",
        "reading_source_id",
        "reading_source_result_id",
        "source_artifact_id",
        "source_byte_length",
        "source_media_type",
        "source_sha256",
    }
)


class PageProjectionPublicationReceiptCodec:
    """Own canonical receipt encoding and exact validated decoding."""

    __slots__ = ("parser",)

    def __init__(self) -> None:
        self.parser = JsonParser(CanonicalJsonSerializer.limits)

    def encode(self, *, receipt: PageProjectionPublicationReceipt) -> str:
        """Encode one exact receipt as canonical transport-safe JSON."""
        if type(receipt) is not PageProjectionPublicationReceipt:
            raise TypeError("receipt has an unsupported type")
        body = CanonicalJsonSerializer.project_object(receipt)
        body["contract_name"] = receipt.CONTRACT_NAME
        body["contract_version"] = receipt.CONTRACT_VERSION
        body["extraction_warning_codes"] = (
            receipt.extraction_warning_codes.values()
        )
        body["reading_limitation_codes"] = (
            receipt.reading_limitation_codes.values()
        )
        body["page_projection_limitation_codes"] = (
            receipt.page_projection_limitation_codes.values()
        )
        return CanonicalJsonSerializer.serializer.serialize_text(body)

    def decode(self, *, body_json: str) -> PageProjectionPublicationReceipt:
        """Decode only the exact canonical transport-safe receipt schema."""
        value = self.parser.parse_text(body_json)
        if not isinstance(value, dict):
            raise ValueError("publication receipt body must be an object")
        if set(value) != _RECEIPT_FIELDS:
            raise ValueError(
                "publication receipt fields differ from its schema"
            )
        if (
            value.get("contract_name")
            != PageProjectionPublicationReceipt.CONTRACT_NAME
            or value.get("contract_version")
            != PageProjectionPublicationReceipt.CONTRACT_VERSION
        ):
            raise ValueError("publication receipt contract is unsupported")
        receipt = PageProjectionPublicationReceipt(
            pipeline_configuration_id=require_publication_receipt_string(
                value.get("pipeline_configuration_id")
            ),
            source_artifact_id=require_publication_receipt_string(
                value.get("source_artifact_id")
            ),
            source_sha256=SHA256Hash(
                require_publication_receipt_string(value.get("source_sha256"))
            ),
            source_byte_length=require_publication_receipt_integer(
                value.get("source_byte_length")
            ),
            source_media_type=require_publication_receipt_string(
                value.get("source_media_type")
            ),
            artifact_verification_result_id=require_publication_receipt_string(
                value.get("artifact_verification_result_id")
            ),
            extraction_manifest_id=require_publication_receipt_string(
                value.get("extraction_manifest_id")
            ),
            extracted_document_id=require_publication_receipt_string(
                value.get("extracted_document_id")
            ),
            reading_source_id=require_publication_receipt_string(
                value.get("reading_source_id")
            ),
            reading_document_id=require_publication_receipt_string(
                value.get("reading_document_id")
            ),
            reading_projection_result_id=require_publication_receipt_string(
                value.get("reading_projection_result_id")
            ),
            reading_inventory_id=require_publication_receipt_string(
                value.get("reading_inventory_id")
            ),
            reading_source_result_id=require_publication_receipt_string(
                value.get("reading_source_result_id")
            ),
            page_projection_result_id=require_publication_receipt_string(
                value.get("page_projection_result_id")
            ),
            page_projection_inventory_id=require_publication_receipt_string(
                value.get("page_projection_inventory_id")
            ),
            enrichment_result_id=require_publication_receipt_string(
                value.get("enrichment_result_id")
            ),
            enrichment_inventory_id=require_publication_receipt_string(
                value.get("enrichment_inventory_id")
            ),
            page_count=require_publication_receipt_integer(
                value.get("page_count")
            ),
            block_count=require_publication_receipt_integer(
                value.get("block_count")
            ),
            enrichment_available_count=require_publication_receipt_integer(
                value.get("enrichment_available_count")
            ),
            enrichment_unavailable_count=require_publication_receipt_integer(
                value.get("enrichment_unavailable_count")
            ),
            extraction_warning_count=require_publication_receipt_integer(
                value.get("extraction_warning_count")
            ),
            extraction_warning_codes=require_publication_receipt_codes(
                value.get("extraction_warning_codes")
            ),
            reading_limitation_count=require_publication_receipt_integer(
                value.get("reading_limitation_count")
            ),
            reading_limitation_codes=require_publication_receipt_codes(
                value.get("reading_limitation_codes")
            ),
            page_projection_limitation_count=(
                require_publication_receipt_integer(
                    value.get("page_projection_limitation_count")
                )
            ),
            page_projection_limitation_codes=(
                require_publication_receipt_codes(
                    value.get("page_projection_limitation_codes")
                )
            ),
            payload_id=require_publication_receipt_string(
                value.get("payload_id")
            ),
            payload_sha256=SHA256Hash(
                require_publication_receipt_string(value.get("payload_sha256"))
            ),
            payload_byte_length=require_publication_receipt_integer(
                value.get("payload_byte_length")
            ),
        )
        if (
            value.get("publication_id") != receipt.publication_id
            or self.encode(receipt=receipt) != body_json
        ):
            raise ValueError("publication receipt identity or encoding differs")
        return receipt


def require_publication_receipt_string(value: JsonValue | None) -> str:
    """Return one exact bounded receipt string."""
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8", errors="strict")) > 4_096
    ):
        raise ValueError("publication receipt string is invalid")
    return value


def require_publication_receipt_integer(value: JsonValue | None) -> int:
    """Return one exact nonnegative receipt integer."""
    if type(value) is not int or value < 0:
        raise ValueError("publication receipt integer is invalid")
    return value


def require_publication_receipt_codes(
    value: JsonValue | None,
) -> PageProjectionPublicationCodeInventory:
    """Return one exact sorted safe receipt code inventory."""
    if not isinstance(value, list):
        raise ValueError("publication receipt codes are invalid")
    codes: list[str] = []
    for item in value:
        if type(item) is not str:
            raise ValueError("publication receipt codes are invalid")
        codes.append(item)
    return PageProjectionPublicationCodeInventory(*codes)
