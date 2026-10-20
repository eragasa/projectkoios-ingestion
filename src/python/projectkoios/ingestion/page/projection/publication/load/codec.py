"""Strict current-schema reconstruction of private publication payloads."""

from __future__ import annotations

import types
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Union, cast, get_args, get_origin, get_type_hints

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.artifact.managed.verification.evidence import (
    ManagedArtifactVerificationEvidence,
    ManagedArtifactVerificationEvidenceInventory,
)
from projectkoios.ingestion.artifact.managed.verification.request import (
    ManagedArtifactVerificationRequest,
)
from projectkoios.ingestion.artifact.managed.verification.result import (
    ManagedArtifactVerificationResult,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.page.projection.block import (
    PageProjectionTextBlock,
    PageProjectionTextBlockInventory,
    PageProjectionTextBlockStyle,
)
from projectkoios.ingestion.page.projection.enrichment.basis import (
    PageProjectionEvidenceRetainedTextBasis,
    PageProjectionEvidenceStyle,
    PageProjectionEvidenceUnavailableReason,
    PageProjectionEvidenceWarningDetailStatus,
)
from projectkoios.ingestion.page.projection.enrichment.binding import (
    PageProjectionEvidenceCrossBinding,
)
from projectkoios.ingestion.page.projection.enrichment.identity import (
    PageProjectionEvidenceAffectedIdentity,
    PageProjectionEvidenceAffectedIdentityInventory,
    PageProjectionEvidenceIdentityInventory,
)
from projectkoios.ingestion.page.projection.enrichment.inventory import (
    PageProjectionEvidenceEnrichmentInventory,
)
from projectkoios.ingestion.page.projection.enrichment.limitation import (
    PageProjectionEvidenceLimitation,
    PageProjectionEvidenceLimitationCode,
    PageProjectionEvidenceLimitationInventory,
)
from projectkoios.ingestion.page.projection.enrichment.producer import (
    PageProjectionEvidenceProducerBinding,
    PageProjectionEvidenceProducerBindingInventory,
)
from projectkoios.ingestion.page.projection.enrichment.record import (
    PageProjectionEvidenceEnrichment,
    PageProjectionEvidenceUnavailable,
)
from projectkoios.ingestion.page.projection.enrichment.request import (
    PageProjectionEvidenceEnrichmentRequest,
)
from projectkoios.ingestion.page.projection.enrichment.result import (
    PageProjectionEvidenceEnrichmentResult,
)
from projectkoios.ingestion.page.projection.enrichment.warning import (
    PageProjectionEvidenceWarning,
    PageProjectionEvidenceWarningInventory,
)
from projectkoios.ingestion.page.projection.limitation import (
    PageProjectionLimitation,
    PageProjectionLimitationInventory,
)
from projectkoios.ingestion.page.projection.page import (
    PageProjectionPage,
    PageProjectionPageInventory,
)
from projectkoios.ingestion.page.projection.publication.code import (
    PageProjectionPublicationCodeInventory,
)
from projectkoios.ingestion.page.projection.publication.evidence import (
    PageProjectionPublicationEvidence,
)
from projectkoios.ingestion.page.projection.request import PageProjectionRequest
from projectkoios.ingestion.page.projection.result import PageProjectionResult
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
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
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.document import (
    ReadingDocumentProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.inventory import (  # noqa: E501
    ReadingEquationProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.source import (  # noqa: E501
    ReadingSourceBlockIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.inventory import (  # noqa: E501
    ReadingTextTransformationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.measures import (  # noqa: E501
    ReadingEvidenceInventoryMeasures,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.code import (
    ReadingEvidenceLimitationCode,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.definition import (  # noqa: E501
    ReadingEvidenceLimitation,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.lineage.definition import (  # noqa: E501
    ReadingEvidenceLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)
from projectkoios.ingestion.transcript.reading.evidence.span.evidence import (
    ReadingSourceSpanEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.span.geometry import (
    ReadingBoundingBox,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.evidence import (
    ReadingTextStreamEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.basis import (  # noqa: E501
    ReadingTextSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.definition import (  # noqa: E501
    ReadingTextSelection,
)

_CURRENT_TYPES = frozenset(
    {
        ManagedArtifactReference,
        ManagedArtifactVerificationEvidence,
        ManagedArtifactVerificationRequest,
        ManagedArtifactVerificationResult,
        PageProjectionEvidenceAffectedIdentity,
        PageProjectionEvidenceCrossBinding,
        PageProjectionEvidenceEnrichment,
        PageProjectionEvidenceEnrichmentRequest,
        PageProjectionEvidenceEnrichmentResult,
        PageProjectionEvidenceLimitation,
        PageProjectionEvidenceProducerBinding,
        PageProjectionEvidenceUnavailable,
        PageProjectionEvidenceWarning,
        PageProjectionPage,
        PageProjectionRequest,
        PageProjectionResult,
        PageProjectionTextBlock,
        ReadingBoundingBox,
        ReadingCleanTextProducerEvidence,
        ReadingDocumentProducerEvidence,
        ReadingEvidenceDocument,
        ReadingEvidenceIdentity,
        ReadingEvidenceInventory,
        ReadingEvidenceInventoryMeasures,
        ReadingEvidenceLimitation,
        ReadingEvidenceLineage,
        ReadingEvidencePage,
        ReadingPageLocation,
        ReadingSourceSpanEvidence,
        ReadingStructuredItemProducerEvidence,
        ReadingTextEvidenceBlock,
        ReadingTextStreamEvidence,
        ReadingEvidenceSourceRequest,
        ReadingEvidenceSourceResult,
    }
)
_CURRENT_ENUMS = frozenset(
    {
        ManagedArtifactMediaType,
        PageProjectionEvidenceLimitationCode,
        PageProjectionEvidenceRetainedTextBasis,
        PageProjectionEvidenceStyle,
        PageProjectionEvidenceUnavailableReason,
        PageProjectionEvidenceWarningDetailStatus,
        PageProjectionLimitation,
        PageProjectionTextBlockStyle,
        ReadingEvidenceBlockKind,
        ReadingEvidenceIdentityKind,
        ReadingEvidenceLimitationCode,
        ReadingReviewStatus,
        ReadingStructuredItemKind,
        ReadingTextBlockProjectionBasis,
        ReadingTextSelectionBasis,
        ReadingTextStreamKind,
    }
)
_SEQUENCE_INVENTORIES: dict[type[object], str] = {
    ManagedArtifactReferenceInventory: "_references",
    PageProjectionEvidenceAffectedIdentityInventory: "_references",
    PageProjectionEvidenceEnrichmentInventory: "_entries",
    PageProjectionEvidenceIdentityInventory: "_identities",
    PageProjectionEvidenceLimitationInventory: "_limitations",
    PageProjectionEvidenceProducerBindingInventory: "_bindings",
    PageProjectionEvidenceWarningInventory: "_warnings",
    PageProjectionPageInventory: "_pages",
    PageProjectionTextBlockInventory: "_blocks",
    ReadingEquationProducerEvidenceInventory: "_records",
    ReadingEvidenceBlockInventory: "_blocks",
    ReadingEvidenceLimitationInventory: "_limitations",
    ReadingEvidencePageInventory: "_pages",
    ReadingFigureProducerEvidenceInventory: "_records",
    ReadingSourceBlockIdentityInventory: "_identities",
    ReadingSourceSpanEvidenceInventory: "_spans",
    ReadingTableProducerEvidenceInventory: "_records",
    ReadingTextBlockSourceInventory: "_records",
    ReadingTextStreamEvidenceInventory: "_streams",
    ReadingTextTransformationInventory: "_transformations",
}


class PageProjectionPublicationPayloadCodec:
    """Decode only the exact canonical current publication payload schema."""

    __slots__ = ("parser",)

    def __init__(self) -> None:
        self.parser = JsonParser(CanonicalJsonSerializer.limits)

    def decode(self, *, payload: bytes) -> PageProjectionPublicationEvidence:
        """Reconstruct exact owner types and require canonical byte replay."""
        value = self.parser.parse_bytes(payload)
        root = require_object(value, "publication payload")
        require_fields(
            root,
            {
                "contract_name",
                "contract_version",
                "enrichment",
                "extracted_document_id",
                "extraction_manifest_id",
                "extraction_warning_codes",
                "extraction_warning_count",
            },
        )
        if (
            root["contract_name"]
            != PageProjectionPublicationEvidence.CONTRACT_NAME
            or root["contract_version"]
            != PageProjectionPublicationEvidence.CONTRACT_VERSION
        ):
            raise JsonParseError("publication payload schema is unsupported")
        enrichment = decode_current_value(
            PageProjectionEvidenceEnrichmentResult,
            root["enrichment"],
        )
        if type(enrichment) is not PageProjectionEvidenceEnrichmentResult:
            raise JsonParseError("publication enrichment type differs")
        warning_values = require_array(
            root["extraction_warning_codes"],
            "extraction warning codes",
        )
        warning_codes = PageProjectionPublicationCodeInventory(
            *(
                require_string(item, "extraction warning code")
                for item in warning_values
            )
        )
        evidence = PageProjectionPublicationEvidence(
            extraction_manifest_id=require_string(
                root["extraction_manifest_id"], "extraction_manifest_id"
            ),
            extracted_document_id=require_string(
                root["extracted_document_id"], "extracted_document_id"
            ),
            extraction_warning_count=require_integer(
                root["extraction_warning_count"], "extraction_warning_count"
            ),
            extraction_warning_codes=warning_codes,
            enrichment=enrichment,
        )
        if evidence.payload_bytes() != payload:
            raise JsonParseError(
                "publication payload is noncanonical or identities differ"
            )
        return evidence


def decode_current_value(expected: object, value: JsonValue) -> object:
    """Reconstruct one value from the closed current payload grammar."""
    if expected is Any:
        raise JsonParseError("unbounded payload types are unsupported")
    alias_value = getattr(expected, "__value__", None)
    if alias_value is not None:
        return decode_current_value(alias_value, value)
    if expected is type(None):
        if value is not None:
            raise JsonParseError("payload value must be null")
        return None
    if expected is bool:
        if type(value) is not bool:
            raise JsonParseError("payload value must be a boolean")
        return value
    if expected is int:
        return require_integer(value, "payload integer")
    if expected is float:
        if type(value) is not float:
            raise JsonParseError("payload value must be a float")
        return value
    if expected is str:
        return require_string(value, "payload string")
    if expected is SHA256Hash:
        return SHA256Hash(require_string(value, "payload SHA-256"))
    origin = get_origin(expected)
    if origin in (Union, types.UnionType):
        successes: list[object] = []
        for member in get_args(expected):
            try:
                successes.append(decode_current_value(member, value))
            except JsonParseError, TypeError, ValueError:
                continue
        if len(successes) != 1:
            raise JsonParseError("payload union value is ambiguous or invalid")
        return successes[0]
    if origin is tuple:
        values = require_array(value, "payload tuple")
        arguments = get_args(expected)
        if len(arguments) != 2 or arguments[1] is not Ellipsis:
            raise JsonParseError("fixed payload tuples are unsupported")
        return tuple(
            decode_current_value(arguments[0], item) for item in values
        )
    if isinstance(expected, type) and issubclass(expected, Enum):
        if expected not in _CURRENT_ENUMS:
            raise JsonParseError("payload enum type is unsupported")
        try:
            return expected(require_string(value, "payload enum"))
        except ValueError as error:
            raise JsonParseError("payload enum value is unsupported") from error
    if expected is ReadingPageTextProducerEvidence:
        return decode_page_text(value)
    if expected is ManagedArtifactVerificationResult:
        return decode_verification_result(value)
    if expected is ReadingEvidenceIdentityInventory:
        return decode_identity_inventory(value)
    if expected is ReadingTextSelection:
        raise JsonParseError(
            "text selection requires its exact stream inventory"
        )
    if expected is ManagedArtifactVerificationEvidenceInventory:
        raise JsonParseError("verification inventory requires its request")
    if expected is PageProjectionLimitationInventory:
        raw = require_object(value, "page-projection limitations")
        require_fields(raw, {"_limitations", "inventory_id"})
        instance = PageProjectionLimitationInventory()
        return require_projected_equality(instance, raw)
    if isinstance(expected, type) and expected in _SEQUENCE_INVENTORIES:
        return decode_sequence_inventory(expected, value)
    if not isinstance(expected, type) or expected not in _CURRENT_TYPES:
        raise JsonParseError("payload value type is unsupported")
    if not is_dataclass(expected):
        raise JsonParseError("payload value type is not a dataclass")
    return decode_regular_dataclass(expected, value)


def decode_regular_dataclass(
    expected: type[object], value: JsonValue
) -> object:
    """Construct one admitted dataclass through its public constructor."""
    raw = require_object(value, expected.__name__)
    definitions = tuple(fields(cast(Any, expected)))
    require_fields(raw, {item.name for item in definitions})
    hints = get_type_hints(expected)
    initial = {
        item.name: decode_current_value(hints[item.name], raw[item.name])
        for item in definitions
        if item.init
    }
    try:
        return expected(**initial)
    except (TypeError, ValueError) as error:
        raise JsonParseError(f"{expected.__name__} is invalid") from error


def decode_sequence_inventory(
    expected: type[object], value: JsonValue
) -> object:
    """Construct one admitted sequence inventory and verify derived fields."""
    raw = require_object(value, expected.__name__)
    definitions = tuple(fields(cast(Any, expected)))
    require_fields(raw, {item.name for item in definitions})
    sequence_name = _SEQUENCE_INVENTORIES[expected]
    sequence_hint = get_type_hints(expected)[sequence_name]
    arguments = get_args(sequence_hint)
    if len(arguments) != 2 or arguments[1] is not Ellipsis:
        raise JsonParseError("payload inventory item schema is unsupported")
    items = tuple(
        decode_current_value(arguments[0], item)
        for item in require_array(raw[sequence_name], sequence_name)
    )
    try:
        instance = expected(*items)
    except (TypeError, ValueError) as error:
        raise JsonParseError(f"{expected.__name__} is invalid") from error
    return require_projected_equality(instance, raw)


def decode_identity_inventory(
    value: JsonValue,
) -> ReadingEvidenceIdentityInventory:
    """Construct one role-homogeneous reading identity inventory."""
    raw = require_object(value, "reading identity inventory")
    require_fields(raw, {"kind", "_identities"})
    kind = decode_current_value(ReadingEvidenceIdentityKind, raw["kind"])
    if not isinstance(kind, ReadingEvidenceIdentityKind):
        raise JsonParseError("reading identity inventory kind is invalid")
    identities = tuple(
        cast(
            ReadingEvidenceIdentity,
            decode_current_value(ReadingEvidenceIdentity, item),
        )
        for item in require_array(raw["_identities"], "reading identities")
    )
    instance = ReadingEvidenceIdentityInventory(kind, *identities)
    return cast(
        ReadingEvidenceIdentityInventory,
        require_projected_equality(instance, raw),
    )


def decode_page_text(value: JsonValue) -> ReadingPageTextProducerEvidence:
    """Reconstruct page text and its stream-bound selection exactly."""
    raw = require_object(value, "page text producer")
    definitions = tuple(fields(ReadingPageTextProducerEvidence))
    require_fields(raw, {item.name for item in definitions})
    streams = decode_current_value(
        ReadingTextStreamEvidenceInventory,
        raw["streams"],
    )
    if type(streams) is not ReadingTextStreamEvidenceInventory:
        raise JsonParseError("page text streams type differs")
    selection_raw = require_object(raw["selection"], "text selection")
    require_fields(
        selection_raw,
        {
            "selection_id",
            "page_location",
            "selected_stream_id",
            "basis",
            "producer_id",
            "composition_id",
        },
    )
    selected_stream_id = decode_current_value(
        ReadingEvidenceIdentity,
        selection_raw["selected_stream_id"],
    )
    basis = decode_current_value(
        ReadingTextSelectionBasis,
        selection_raw["basis"],
    )
    if type(
        selected_stream_id
    ) is not ReadingEvidenceIdentity or not isinstance(
        basis, ReadingTextSelectionBasis
    ):
        raise JsonParseError("text selection constructor values differ")
    selection = ReadingTextSelection(
        streams=streams,
        selected_stream_id=selected_stream_id,
        basis=basis,
    )
    require_projected_equality(selection, selection_raw)
    producer_id = decode_current_value(
        ReadingEvidenceIdentity, raw["producer_id"]
    )
    review_status = decode_current_value(
        ReadingReviewStatus, raw["review_status"]
    )
    if type(producer_id) is not ReadingEvidenceIdentity or not isinstance(
        review_status, ReadingReviewStatus
    ):
        raise JsonParseError("page text constructor values differ")
    instance = ReadingPageTextProducerEvidence(
        streams=streams,
        selection=selection,
        producer_id=producer_id,
        producer_version=require_string(
            raw["producer_version"], "producer_version"
        ),
        review_status=review_status,
    )
    return cast(
        ReadingPageTextProducerEvidence,
        require_projected_equality(instance, raw),
    )


def decode_verification_result(
    value: JsonValue,
) -> ManagedArtifactVerificationResult:
    """Reconstruct verification using its exact requested references."""
    raw = require_object(value, "managed artifact verification result")
    definitions = tuple(fields(ManagedArtifactVerificationResult))
    require_fields(raw, {item.name for item in definitions})
    request = decode_current_value(
        ManagedArtifactVerificationRequest,
        raw["request"],
    )
    if type(request) is not ManagedArtifactVerificationRequest:
        raise JsonParseError("verification request type differs")
    evidence_raw = require_object(raw["evidence"], "verification evidence")
    evidence_definitions = tuple(
        fields(ManagedArtifactVerificationEvidenceInventory)
    )
    require_fields(evidence_raw, {item.name for item in evidence_definitions})
    evidence = tuple(
        cast(
            ManagedArtifactVerificationEvidence,
            decode_current_value(ManagedArtifactVerificationEvidence, item),
        )
        for item in require_array(
            evidence_raw["_evidence"], "verification evidence"
        )
    )
    inventory = ManagedArtifactVerificationEvidenceInventory(
        request.references,
        *evidence,
    )
    require_projected_equality(inventory, evidence_raw)
    instance = ManagedArtifactVerificationResult(
        request=request,
        evidence=inventory,
        verifier_implementation_id=require_string(
            raw["verifier_implementation_id"],
            "verifier_implementation_id",
        ),
    )
    return cast(
        ManagedArtifactVerificationResult,
        require_projected_equality(instance, raw),
    )


def require_projected_equality(
    instance: object, raw: dict[str, JsonValue]
) -> object:
    """Require stored initial and derived fields to equal reconstruction."""
    if CanonicalJsonSerializer.project_object(instance) != raw:
        raise JsonParseError("stored fields differ from reconstructed values")
    return instance


def require_object(value: JsonValue, name: str) -> dict[str, JsonValue]:
    """Return one exact JSON object."""
    if type(value) is not dict:
        raise JsonParseError(f"{name} must be an object")
    return value


def require_array(value: JsonValue, name: str) -> list[JsonValue]:
    """Return one exact JSON array."""
    if type(value) is not list:
        raise JsonParseError(f"{name} must be an array")
    return value


def require_fields(value: dict[str, JsonValue], expected: set[str]) -> None:
    """Require one closed exact field set."""
    if set(value) != expected:
        raise JsonParseError("payload fields differ from current schema")


def require_string(value: JsonValue, name: str) -> str:
    """Return one exact string."""
    if type(value) is not str:
        raise JsonParseError(f"{name} must be a string")
    return value


def require_integer(value: JsonValue, name: str) -> int:
    """Return one exact integer."""
    if type(value) is not int:
        raise JsonParseError(f"{name} must be an integer")
    return value
