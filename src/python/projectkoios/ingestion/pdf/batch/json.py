"""Typed bounded JSON boundary for version-1 PDF batch plans."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import ClassVar

from projectkoios.ingestion.json.contract import JsonContract
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.serializer import JsonSerializer
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.pdf.batch.item import PdfBatchItem
from projectkoios.ingestion.pdf.batch.limits.definition import (
    MAX_PDF_BATCH_JSON_BYTES,
    MAX_PDF_BATCH_JSON_CONTAINER_DEPTH,
    MAX_PDF_BATCH_JSON_ITEMS,
    MAX_PDF_BATCH_JSON_NUMBER_CHARACTERS,
    MAX_PDF_BATCH_JSON_STRING_BYTES,
    MAX_PDF_BATCH_JSON_TOTAL_STRING_BYTES,
    MAX_PDF_BATCH_TEXT_CHARACTERS,
)
from projectkoios.ingestion.pdf.batch.limits.error import PdfBatchLimitError
from projectkoios.ingestion.pdf.batch.plan import PdfBatchPlan


class PdfBatchPlanJsonContract(JsonContract[PdfBatchPlan]):
    """Reconstruct and serialize the exact version-1 PDF batch schema."""

    __slots__ = ()

    limits: ClassVar[JsonLimits] = JsonLimits(
        maximum_utf8_bytes=MAX_PDF_BATCH_JSON_BYTES,
        maximum_container_depth=MAX_PDF_BATCH_JSON_CONTAINER_DEPTH,
        maximum_items=MAX_PDF_BATCH_JSON_ITEMS,
        maximum_string_bytes=MAX_PDF_BATCH_JSON_STRING_BYTES,
        maximum_total_string_bytes=MAX_PDF_BATCH_JSON_TOTAL_STRING_BYTES,
        maximum_number_characters=MAX_PDF_BATCH_JSON_NUMBER_CHARACTERS,
    )
    _parser: ClassVar[JsonParser] = JsonParser(limits)
    _serializer: ClassVar[JsonSerializer] = JsonSerializer.durable_pretty(
        limits=limits,
        sort_keys=False,
    )

    @property
    def parser(self) -> JsonParser:
        return self._parser

    @property
    def serializer(self) -> JsonSerializer:
        return self._serializer

    def to_json_value(self, value: PdfBatchPlan) -> JsonValue:
        if type(value) is not PdfBatchPlan:
            raise TypeError("value must be a PdfBatchPlan")
        return {
            "schema_version": value.schema_version,
            "items": [
                {
                    "source_id": item.source_id,
                    "pdf_path": item.pdf_path.as_posix(),
                    "output_directory": item.output_directory.as_posix(),
                    "sha256": item.sha256,
                    "byte_size": item.byte_size,
                    "locator": item.locator,
                }
                for item in value.items
            ],
        }

    def from_json_value(self, value: JsonValue) -> PdfBatchPlan:
        if not isinstance(value, dict):
            raise ValueError("PDF batch plan must be an object")
        unknown = set(value) - {"schema_version", "items"}
        if unknown:
            raise ValueError(
                f"unknown PDF batch-plan fields: {sorted(unknown)}"
            )
        schema_version = value.get("schema_version")
        items = value.get("items")
        if type(schema_version) is not int:
            raise ValueError("schema_version must be an integer")
        if not isinstance(items, list):
            raise ValueError("items must be an array")
        return PdfBatchPlan(
            schema_version=schema_version,
            items=tuple(self.item_from_json_value(item) for item in items),
        )

    def serialize_text(self, value: PdfBatchPlan) -> str:
        try:
            return super().serialize_text(value)
        except JsonLimitError as error:
            raise PdfBatchLimitError(str(error)) from error

    def serialize_bytes(self, value: PdfBatchPlan) -> bytes:
        try:
            return super().serialize_bytes(value)
        except JsonLimitError as error:
            raise PdfBatchLimitError(str(error)) from error

    def parse_text(self, content: str) -> PdfBatchPlan:
        try:
            return super().parse_text(content)
        except JsonLimitError as error:
            raise PdfBatchLimitError(str(error)) from error

    def parse_bytes(self, content: bytes) -> PdfBatchPlan:
        try:
            return super().parse_bytes(content)
        except JsonLimitError as error:
            raise PdfBatchLimitError(str(error)) from error

    @classmethod
    def item_from_json_value(cls, value: JsonValue) -> PdfBatchItem:
        if not isinstance(value, dict):
            raise ValueError("batch item must be an object")
        expected = {
            "source_id",
            "pdf_path",
            "output_directory",
            "sha256",
            "byte_size",
            "locator",
        }
        unknown = set(value) - expected
        if unknown:
            raise ValueError(f"unknown batch item fields: {sorted(unknown)}")
        missing = expected - set(value)
        if missing:
            raise ValueError(f"missing batch item fields: {sorted(missing)}")
        source_id = value.get("source_id")
        locator = value.get("locator")
        sha256 = value.get("sha256")
        byte_size = value.get("byte_size")
        if not isinstance(source_id, str):
            raise ValueError("source_id must be a string")
        if locator is not None and not isinstance(locator, str):
            raise ValueError("locator must be a string or null")
        if not isinstance(sha256, str):
            raise ValueError("sha256 must be a string")
        if type(byte_size) is not int:
            raise ValueError("byte_size must be an integer")
        return PdfBatchItem(
            source_id=source_id,
            pdf_path=cls._relative_path(
                value.get("pdf_path"),
                field="pdf_path",
            ),
            output_directory=cls._relative_path(
                value.get("output_directory"),
                field="output_directory",
            ),
            sha256=sha256,
            byte_size=byte_size,
            locator=locator,
        )

    @staticmethod
    def _relative_path(value: JsonValue, *, field: str) -> PurePosixPath:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string")
        if len(value) > MAX_PDF_BATCH_TEXT_CHARACTERS:
            raise PdfBatchLimitError(f"{field} is too long")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError(f"{field} must be a safe relative path")
        if any(part in ("", ".") for part in path.parts):
            raise ValueError(f"{field} must be normalized")
        if path.as_posix() != value:
            raise ValueError(f"{field} must be normalized")
        return path
