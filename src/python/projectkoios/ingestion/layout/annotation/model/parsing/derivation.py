"""Pure derivation of strict model-response parsing evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar, cast

from projectkoios.ingestion.json.error import JsonParseError
from projectkoios.ingestion.json.limits.definition import JsonLimits
from projectkoios.ingestion.json.limits.error import JsonLimitError
from projectkoios.ingestion.json.parser import JsonParser
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.layout.annotation.failure import (
    LayoutFailureAnnotation,
)
from projectkoios.ingestion.layout.annotation.kind import (
    LayoutAnnotationOutcome,
    LayoutFailureKind,
)
from projectkoios.ingestion.layout.annotation.limits.definition import (
    MAX_LAYOUT_ANNOTATIONS_PER_KIND,
    MAX_LAYOUT_REFERENCES_PER_ANNOTATION,
)
from projectkoios.ingestion.layout.annotation.model.candidate import (
    LayoutModelAnnotationCandidate,
)
from projectkoios.ingestion.layout.annotation.model.invocation import (
    LayoutAnnotationModelInvocationStatus,
)
from projectkoios.ingestion.layout.annotation.model.limitation import (
    LayoutModelAnnotationLimitation,
    LayoutModelAnnotationLimitationCode,
)
from projectkoios.ingestion.layout.annotation.model.parsing.request import (
    LayoutModelResponseParsingRequest,
)
from projectkoios.ingestion.layout.annotation.model.parsing.status import (
    LayoutModelResponseParsingStatus,
)
from projectkoios.ingestion.layout.annotation.order import (
    LayoutReadingOrderAnnotation,
)
from projectkoios.ingestion.layout.annotation.region import (
    LayoutRegionAnnotation,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind

EnumT = TypeVar("EnumT", bound=StrEnum)


class LayoutModelResponseSchemaError(ValueError):
    """Signal a closed-schema mismatch without retaining model text."""


@dataclass(frozen=True, slots=True)
class LayoutModelResponseInterpretation:
    """Expected parsing evidence derived from one exact invocation."""

    status: LayoutModelResponseParsingStatus
    candidate: LayoutModelAnnotationCandidate | None
    limitation: LayoutModelAnnotationLimitation | None


class LayoutModelResponseInterpreter:
    """Own strict bounded interpretation of exact raw model response bytes."""

    __slots__ = ()

    @classmethod
    def interpret(
        cls,
        request: LayoutModelResponseParsingRequest,
    ) -> LayoutModelResponseInterpretation:
        """Derive the only valid parsing outcome for one exact invocation."""
        if type(request) is not LayoutModelResponseParsingRequest:
            raise TypeError("request must be LayoutModelResponseParsingRequest")
        invocation = request.invocation
        if (
            invocation.status
            is not LayoutAnnotationModelInvocationStatus.COMPLETE
        ):
            return cls.rejected(
                request,
                LayoutModelAnnotationLimitationCode.INVOCATION_FAILED,
            )
        if invocation.raw_response_bytes is None:
            raise RuntimeError("complete invocation omitted raw response bytes")
        limits = JsonLimits(
            maximum_utf8_bytes=(
                invocation.request.configuration.maximum_response_bytes
            ),
            maximum_container_depth=16,
            maximum_items=200_000,
            maximum_string_bytes=64_000,
            maximum_total_string_bytes=(
                invocation.request.configuration.maximum_response_bytes
            ),
            maximum_number_characters=128,
        )
        try:
            value = JsonParser(limits).parse_bytes(
                invocation.raw_response_bytes
            )
        except JsonParseError, JsonLimitError:
            return cls.rejected(
                request,
                LayoutModelAnnotationLimitationCode.MALFORMED_JSON,
            )
        try:
            candidate = cls.parse_candidate(request, value)
        except LayoutModelResponseSchemaError:
            return cls.rejected(
                request,
                LayoutModelAnnotationLimitationCode.INVALID_SCHEMA,
            )
        except TypeError, ValueError:
            return cls.rejected(
                request,
                LayoutModelAnnotationLimitationCode.INVALID_ANNOTATION,
            )
        return LayoutModelResponseInterpretation(
            status=LayoutModelResponseParsingStatus.PARSED,
            candidate=candidate,
            limitation=None,
        )

    @staticmethod
    def rejected(
        request: LayoutModelResponseParsingRequest,
        code: LayoutModelAnnotationLimitationCode,
    ) -> LayoutModelResponseInterpretation:
        """Derive one invocation-bound rejected interpretation."""
        limitation = LayoutModelAnnotationLimitation(
            case_id=request.invocation.request.case.case_id,
            code=code,
            affected_invocation_ids=(request.invocation.invocation_id,),
        )
        return LayoutModelResponseInterpretation(
            status=LayoutModelResponseParsingStatus.REJECTED,
            candidate=None,
            limitation=limitation,
        )

    @classmethod
    def parse_candidate(
        cls,
        request: LayoutModelResponseParsingRequest,
        value: JsonValue,
    ) -> LayoutModelAnnotationCandidate:
        """Decode one exact closed response object into domain values."""
        root = cls.require_object(
            value,
            {
                "schema_version",
                "case_id",
                "outcome",
                "regions",
                "order_edges",
                "failures",
            },
        )
        if (
            type(root["schema_version"]) is not int
            or root["schema_version"] != 1
        ):
            raise LayoutModelResponseSchemaError(
                "schema_version must equal one"
            )
        case = request.invocation.request.case
        if root["case_id"] != case.case_id:
            raise LayoutModelResponseSchemaError("case_id does not match")
        outcome = cls.require_enum(root["outcome"], LayoutAnnotationOutcome)
        region_values = cls.require_array(
            root["regions"], MAX_LAYOUT_ANNOTATIONS_PER_KIND
        )
        regions = tuple(
            cls.parse_region(case.case_id, item) for item in region_values
        )
        edge_values = cls.require_array(
            root["order_edges"], MAX_LAYOUT_ANNOTATIONS_PER_KIND
        )
        order_edges = tuple(
            cls.parse_edge(case.case_id, item) for item in edge_values
        )
        failure_values = cls.require_array(
            root["failures"], MAX_LAYOUT_ANNOTATIONS_PER_KIND
        )
        failures = tuple(
            cls.parse_failure(case.case_id, item, regions)
            for item in failure_values
        )
        return LayoutModelAnnotationCandidate(
            case=case,
            outcome=outcome,
            regions=regions,
            order_edges=order_edges,
            failures=failures,
        )

    @staticmethod
    def require_object(
        value: JsonValue,
        exact_fields: set[str],
    ) -> dict[str, JsonValue]:
        """Require one object with exactly the declared field set."""
        if not isinstance(value, dict) or set(value) != exact_fields:
            raise LayoutModelResponseSchemaError(
                "response object fields do not match the schema"
            )
        return value

    @staticmethod
    def require_array(value: JsonValue, maximum: int) -> list[JsonValue]:
        """Require one bounded JSON array."""
        if not isinstance(value, list) or len(value) > maximum:
            raise LayoutModelResponseSchemaError(
                "response array is invalid or exceeds its limit"
            )
        return value

    @staticmethod
    def require_strings(value: JsonValue) -> tuple[str, ...]:
        """Require one bounded array of exact nonempty strings."""
        if (
            not isinstance(value, list)
            or len(value) > MAX_LAYOUT_REFERENCES_PER_ANNOTATION
            or any(not isinstance(item, str) or not item for item in value)
        ):
            raise LayoutModelResponseSchemaError(
                "identity array must contain bounded nonempty strings"
            )
        return tuple(cast(list[str], value))

    @staticmethod
    def require_enum(value: JsonValue, kind: type[EnumT]) -> EnumT:
        """Require one exact member of a closed string enumeration."""
        if not isinstance(value, str):
            raise LayoutModelResponseSchemaError("enum value must be text")
        try:
            return kind(value)
        except ValueError as error:
            raise LayoutModelResponseSchemaError(
                "enum value is outside the closed vocabulary"
            ) from error

    @classmethod
    def parse_region(
        cls,
        case_id: str,
        value: JsonValue,
    ) -> LayoutRegionAnnotation:
        """Parse one region annotation."""
        item = cls.require_object(
            value,
            {"kind", "bounding_box_pixels", "block_ids"},
        )
        raw_box = item["bounding_box_pixels"]
        if (
            not isinstance(raw_box, list)
            or len(raw_box) != 4
            or any(
                isinstance(coordinate, bool)
                or not isinstance(coordinate, int | float)
                for coordinate in raw_box
            )
        ):
            raise LayoutModelResponseSchemaError(
                "bounding_box_pixels must contain four numbers"
            )
        box = cast(list[int | float], raw_box)
        return LayoutRegionAnnotation.create(
            case_id=case_id,
            kind=cls.require_enum(item["kind"], LayoutRegionKind),
            bounding_box_pixels=(
                float(box[0]),
                float(box[1]),
                float(box[2]),
                float(box[3]),
            ),
            block_ids=tuple(sorted(cls.require_strings(item["block_ids"]))),
        )

    @classmethod
    def parse_edge(
        cls,
        case_id: str,
        value: JsonValue,
    ) -> LayoutReadingOrderAnnotation:
        """Parse one directed reading-order edge."""
        item = cls.require_object(
            value,
            {"before_block_id", "after_block_id"},
        )
        before = item["before_block_id"]
        after = item["after_block_id"]
        if not isinstance(before, str) or not isinstance(after, str):
            raise LayoutModelResponseSchemaError(
                "reading-order endpoints must be strings"
            )
        return LayoutReadingOrderAnnotation.create(
            case_id=case_id,
            before_block_id=before,
            after_block_id=after,
        )

    @classmethod
    def parse_failure(
        cls,
        case_id: str,
        value: JsonValue,
        regions: tuple[LayoutRegionAnnotation, ...],
    ) -> LayoutFailureAnnotation:
        """Parse one failure and resolve bounded region indexes."""
        item = cls.require_object(
            value,
            {"kind", "block_ids", "proposal_ids", "region_indexes"},
        )
        raw_indexes = item["region_indexes"]
        if (
            not isinstance(raw_indexes, list)
            or len(raw_indexes) > MAX_LAYOUT_REFERENCES_PER_ANNOTATION
            or any(type(index) is not int for index in raw_indexes)
        ):
            raise LayoutModelResponseSchemaError(
                "region_indexes contains an invalid reference"
            )
        indexes = cast(list[int], raw_indexes)
        if any(index < 0 or index >= len(regions) for index in indexes):
            raise LayoutModelResponseSchemaError(
                "region_indexes contains an invalid reference"
            )
        return LayoutFailureAnnotation.create(
            case_id=case_id,
            kind=cls.require_enum(item["kind"], LayoutFailureKind),
            block_ids=tuple(sorted(cls.require_strings(item["block_ids"]))),
            proposal_ids=tuple(
                sorted(cls.require_strings(item["proposal_ids"]))
            ),
            region_annotation_ids=tuple(
                sorted(regions[index].region_annotation_id for index in indexes)
            ),
        )
