"""Strict canonical codecs for table proposal and acceptance evidence."""

from __future__ import annotations

import types
from dataclasses import fields
from typing import Any, Union, cast, get_args, get_origin, get_type_hints

from projectkoios.ingestion.identity import sha256_digest
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.tables.acceptance.cell import (
    TableEvidenceProposalCell,
)
from projectkoios.ingestion.tables.acceptance.conflict import (
    TableEvidenceConflictDisposition,
    TableEvidenceConflictKind,
    TableEvidenceConflictResolution,
)
from projectkoios.ingestion.tables.acceptance.decision import (
    TableEvidenceHumanAcceptanceDecision,
)
from projectkoios.ingestion.tables.acceptance.inventory import (
    TableEvidenceConflictInventory,
)
from projectkoios.ingestion.tables.acceptance.observation import (
    TableEvidenceConflictObservation,
)
from projectkoios.ingestion.tables.acceptance.parameter import (
    TableEvidenceParameter,
)
from projectkoios.ingestion.tables.acceptance.proposal import (
    TableEvidenceProposal,
)
from projectkoios.ingestion.tables.acceptance.result import (
    AcceptedTableEvidenceResult,
    AcceptedTableEvidenceStatus,
)
from projectkoios.ingestion.tables.acceptance.row import (
    TableEvidenceProposalRow,
)
from projectkoios.ingestion.tables.acceptance.validation import require_sha256

_CURRENT_TYPES = frozenset(
    {
        AcceptedTableEvidenceResult,
        TableEvidenceConflictDisposition,
        TableEvidenceConflictInventory,
        TableEvidenceConflictObservation,
        TableEvidenceHumanAcceptanceDecision,
        TableEvidenceParameter,
        TableEvidenceProposal,
        TableEvidenceProposalCell,
        TableEvidenceProposalRow,
    }
)
_CURRENT_ENUMS = frozenset(
    {
        AcceptedTableEvidenceStatus,
        TableEvidenceConflictKind,
        TableEvidenceConflictResolution,
    }
)


class TableEvidenceProposalCodec:
    """Load the exact bounded private proposal into immutable owner types."""

    __slots__ = ("parser",)

    def __init__(self) -> None:
        self.parser = JsonParser(CanonicalJsonSerializer.limits)

    def decode(
        self, *, payload: bytes, expected_sha256: str
    ) -> TableEvidenceProposal:
        require_sha256("expected_sha256", expected_sha256)
        if sha256_digest(payload) != expected_sha256:
            raise JsonParseError("table proposal SHA-256 differs")
        root = _object(self.parser.parse_bytes(payload), "table proposal")
        _fields(
            root,
            {
                "acceptance_status",
                "artifact_kind",
                "authority_status",
                "closure",
                "limitations",
                "page",
                "parameters",
                "region",
                "rows",
                "schema_version",
                "source",
                "title_observation",
            },
        )
        if (
            root["artifact_kind"]
            != "private-unaccepted-table-transcription-proposal"
            or root["schema_version"] != 1
            or root["authority_status"] != "not-owner-typed-table-evidence"
            or root["acceptance_status"]
            != "unaccepted-human-proofreading-required"
        ):
            raise JsonParseError(
                "table proposal schema or state is unsupported"
            )
        source = _object(root["source"], "source")
        _fields(
            source,
            {
                "locator",
                "media_type",
                "rights_access_status",
                "source_blob_id",
                "source_byte_length",
                "source_id",
                "source_sha256",
            },
        )
        page = _object(root["page"], "page")
        _fields(
            page,
            {
                "physical_page_index",
                "physical_page_number",
                "printed_label_basis",
                "printed_page_label",
                "reading_page_location_id",
            },
        )
        region = _object(root["region"], "region")
        _fields(
            region,
            {
                "byte_length",
                "content_sha256",
                "coordinate_system",
                "effective_source_bounding_box",
                "height_pixels",
                "rendered_region_id",
                "resolution_dpi",
                "source_bounding_box",
                "width_pixels",
            },
        )
        parameter_values = _array(root["parameters"], "parameters")
        try:
            parameters = tuple(
                self._parameter(item) for item in parameter_values
            )
        except (TypeError, ValueError) as error:
            raise JsonParseError(
                f"table proposal parameter is invalid: {error}"
            ) from None
        row_values = _array(root["rows"], "rows")
        try:
            rows = tuple(self._row(item, parameters) for item in row_values)
        except (TypeError, ValueError) as error:
            raise JsonParseError(
                f"table proposal row is invalid: {error}"
            ) from None
        closure = _object(root["closure"], "closure")
        if (
            closure.get("compound_rows") != len(rows)
            or closure.get("parameter_columns") != len(parameters)
            or closure.get("numeric_parameter_cells")
            != len(rows) * len(parameters)
            or closure.get("typed_authority_closure") is not False
            or closure.get("human_proofreading_closure") is not False
        ):
            raise JsonParseError("proposal closure is inconsistent")
        try:
            return TableEvidenceProposal(
                proposal_sha256=expected_sha256,
                source_id=_string(source["source_id"], "source_id"),
                source_blob_id=_string(
                    source["source_blob_id"], "source_blob_id"
                ),
                source_sha256=_string(source["source_sha256"], "source_sha256"),
                source_byte_length=_integer(
                    source["source_byte_length"], "source_byte_length"
                ),
                source_media_type=_string(source["media_type"], "media_type"),
                rights_access_status=_string(
                    source["rights_access_status"], "rights_access_status"
                ),
                physical_page_index=_integer(
                    page["physical_page_index"], "physical_page_index"
                ),
                physical_page_number=_integer(
                    page["physical_page_number"], "physical_page_number"
                ),
                printed_page_label=_string(
                    page["printed_page_label"], "printed_page_label"
                ),
                reading_page_location_id=_string(
                    page["reading_page_location_id"],
                    "reading_page_location_id",
                ),
                rendered_region_id=_string(
                    region["rendered_region_id"], "rendered_region_id"
                ),
                rendered_region_sha256=_string(
                    region["content_sha256"], "content_sha256"
                ),
                source_bounding_box=_box(
                    region["source_bounding_box"], "source_bounding_box"
                ),
                coordinate_system=_string(
                    region["coordinate_system"], "coordinate_system"
                ),
                resolution_dpi=_integer(
                    region["resolution_dpi"], "resolution_dpi"
                ),
                parameters=parameters,
                rows=rows,
            )
        except (TypeError, ValueError) as error:
            raise JsonParseError(
                f"table proposal is invalid: {error}"
            ) from None

    @staticmethod
    def _parameter(value: object) -> TableEvidenceParameter:
        item = _object(value, "parameter")
        _fields(
            item,
            {
                "parameter_index",
                "parameter_key",
                "printed_header",
                "printed_panel",
                "unit",
            },
        )
        return TableEvidenceParameter(
            parameter_index=_integer(
                item["parameter_index"], "parameter_index"
            ),
            parameter_key=_string(item["parameter_key"], "parameter_key"),
            printed_header=_string(item["printed_header"], "printed_header"),
            unit=_string(item["unit"], "unit"),
            printed_panel=_integer(item["printed_panel"], "printed_panel"),
        )

    @staticmethod
    def _row(
        value: object, parameters: tuple[TableEvidenceParameter, ...]
    ) -> TableEvidenceProposalRow:
        item = _object(value, "row")
        _fields(
            item,
            {"cells", "compound", "compound_observations", "row_index"},
        )
        row_index = _integer(item["row_index"], "row_index")
        cells = tuple(
            TableEvidenceProposalCodec._cell(cell, row_index, parameters)
            for cell in _array(item["cells"], "cells")
        )
        return TableEvidenceProposalRow(
            row_index=row_index,
            compound=_string(item["compound"], "compound"),
            cells=cells,
        )

    @staticmethod
    def _cell(
        value: object,
        row_index: int,
        parameters: tuple[TableEvidenceParameter, ...],
    ) -> TableEvidenceProposalCell:
        item = _object(value, "cell")
        _fields(
            item,
            {
                "ambiguity_flags",
                "independent_ocr_text",
                "native_word_locators",
                "normalized_proposed_text",
                "panel",
                "parameter_index",
                "parameter_key",
                "printed_header",
                "raw_native_text",
                "source_bounding_box",
                "unit",
            },
        )
        parameter_index = _integer(item["parameter_index"], "parameter_index")
        if parameter_index >= len(parameters):
            raise JsonParseError("cell parameter index is outside the proposal")
        return TableEvidenceProposalCell(
            row_index=row_index,
            parameter_index=parameter_index,
            parameter_key=_string(item["parameter_key"], "parameter_key"),
            printed_header=_string(item["printed_header"], "printed_header"),
            unit=_string(item["unit"], "unit"),
            printed_panel=_integer(item["panel"], "panel"),
            raw_native_text=_string(item["raw_native_text"], "raw_native_text"),
            proposed_text=_string(
                item["normalized_proposed_text"],
                "normalized_proposed_text",
            ),
            source_bounding_box=_box(
                item["source_bounding_box"], "source_bounding_box"
            ),
            independent_ocr_text=_string(
                item["independent_ocr_text"], "independent_ocr_text"
            ),
            ambiguity_flags=tuple(
                _string(flag, "ambiguity flag")
                for flag in _array(item["ambiguity_flags"], "ambiguity_flags")
            ),
        )


class AcceptedTableEvidenceCodec:
    """Encode and strictly reconstruct canonical accepted evidence."""

    __slots__ = ("parser",)

    def __init__(self) -> None:
        self.parser = JsonParser(CanonicalJsonSerializer.limits)

    @staticmethod
    def encode(value: object) -> bytes:
        if type(value) not in {
            AcceptedTableEvidenceResult,
            TableEvidenceConflictInventory,
            TableEvidenceHumanAcceptanceDecision,
        }:
            raise TypeError("accepted-table codec cannot encode this type")
        return CanonicalJsonSerializer.serialize_bytes(value)

    def decode_result(self, *, payload: bytes) -> AcceptedTableEvidenceResult:
        value = self.parser.parse_bytes(payload)
        result = _decode_type(AcceptedTableEvidenceResult, value)
        if type(result) is not AcceptedTableEvidenceResult:
            raise JsonParseError("decoded accepted result has the wrong type")
        if self.encode(result) != payload:
            raise JsonParseError(
                "accepted table evidence is noncanonical or identities differ"
            )
        return result

    def decode_inventory(
        self, *, payload: bytes
    ) -> TableEvidenceConflictInventory:
        value = self.parser.parse_bytes(payload)
        inventory = _decode_type(TableEvidenceConflictInventory, value)
        if type(inventory) is not TableEvidenceConflictInventory:
            raise JsonParseError(
                "decoded conflict inventory has the wrong type"
            )
        if self.encode(inventory) != payload:
            raise JsonParseError(
                "conflict inventory is noncanonical or identities differ"
            )
        return inventory

    def decode_decision(
        self, *, payload: bytes
    ) -> TableEvidenceHumanAcceptanceDecision:
        value = self.parser.parse_bytes(payload)
        decision = _decode_type(TableEvidenceHumanAcceptanceDecision, value)
        if type(decision) is not TableEvidenceHumanAcceptanceDecision:
            raise JsonParseError("decoded decision has the wrong type")
        if self.encode(decision) != payload:
            raise JsonParseError(
                "table acceptance decision is noncanonical or identities differ"
            )
        return decision


def _decode_type(expected: object, value: object) -> object:
    origin = get_origin(expected)
    if origin is tuple:
        if not isinstance(value, list):
            raise JsonParseError("expected a JSON array")
        arguments = get_args(expected)
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return tuple(_decode_type(arguments[0], item) for item in value)
        if len(value) != len(arguments):
            raise JsonParseError("fixed tuple length differs")
        return tuple(
            _decode_type(argument, item)
            for argument, item in zip(arguments, value, strict=True)
        )
    if origin in (Union, types.UnionType):
        raise JsonParseError("union fields are unsupported")
    if expected is str:
        return _string(value, "string field")
    if expected is int:
        return _integer(value, "integer field")
    if expected is float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise JsonParseError("expected a JSON number")
        return float(value)
    if isinstance(expected, type) and expected in _CURRENT_ENUMS:
        if not isinstance(value, str):
            raise JsonParseError("expected an enum string")
        try:
            return expected(value)
        except ValueError:
            raise JsonParseError("enum value is unsupported") from None
    if isinstance(expected, type) and expected in _CURRENT_TYPES:
        item = _object(value, expected.__name__)
        type_fields = fields(cast(Any, expected))
        _fields(item, {field.name for field in type_fields})
        hints = get_type_hints(expected)
        kwargs = {
            field.name: _decode_type(hints[field.name], item[field.name])
            for field in type_fields
            if field.init
        }
        try:
            result = expected(**kwargs)
        except (TypeError, ValueError) as error:
            raise JsonParseError(
                f"{expected.__name__} is invalid: {error}"
            ) from None
        for field in type_fields:
            if (
                not field.init
                and getattr(result, field.name) != item[field.name]
            ):
                raise JsonParseError(
                    f"{expected.__name__} identity field is inconsistent"
                )
        return result
    raise JsonParseError("field type is outside the current allowlist")


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in value
    ):
        raise JsonParseError(f"{name} must be a JSON object")
    return value


def _array(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise JsonParseError(f"{name} must be a JSON array")
    return value


def _fields(value: dict[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise JsonParseError(
            "JSON object fields differ from the current schema"
        )


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise JsonParseError(f"{name} must be a string")
    return value


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise JsonParseError(f"{name} must be an integer")
    return value


def _box(value: object, name: str) -> tuple[float, float, float, float]:
    items = _array(value, name)
    if len(items) != 4 or any(
        isinstance(item, bool) or not isinstance(item, int | float)
        for item in items
    ):
        raise JsonParseError(f"{name} must be a four-number array")
    return (float(items[0]), float(items[1]), float(items[2]), float(items[3]))
