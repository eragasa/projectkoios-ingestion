"""Explicit limitations for unusable or unresolved model evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.model.configuration import (
    MAX_LAYOUT_MODEL_REPLICAS,
)
from projectkoios.ingestion.layout.annotation.model.invocation import (
    LayoutAnnotationModelInvocationResult,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash


class LayoutModelAnnotationLimitationCode(StrEnum):
    """Closed reasons that model evidence is not resolution-eligible."""

    INVOCATION_FAILED = "invocation_failed"
    MALFORMED_JSON = "malformed_json"
    INVALID_SCHEMA = "invalid_schema"
    INVALID_ANNOTATION = "invalid_annotation"
    INSUFFICIENT_VALID_RESPONSES = "insufficient_valid_responses"
    CONFLICTING_VALID_RESPONSES = "conflicting_valid_responses"


@dataclass(frozen=True, slots=True)
class LayoutModelAnnotationLimitation(AbstractImmutableDataObject):
    """Identify affected evidence without repairing or accepting it."""

    CONTRACT_NAME: ClassVar[str] = "layout-model-annotation-limitation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    case_id: str
    code: LayoutModelAnnotationLimitationCode
    affected_invocation_ids: tuple[str, ...]
    limitation_id: str = field(init=False)

    def __post_init__(self) -> None:
        case = LayoutValueValidation.require_text("case_id", self.case_id)
        if not isinstance(self.code, LayoutModelAnnotationLimitationCode):
            raise TypeError("code must be LayoutModelAnnotationLimitationCode")
        if not isinstance(self.affected_invocation_ids, tuple) or not (
            1 <= len(self.affected_invocation_ids) <= MAX_LAYOUT_MODEL_REPLICAS
        ):
            raise ValueError(
                "affected_invocation_ids must be a bounded nonempty tuple"
            )
        affected = tuple(
            LayoutValueValidation.require_text("invocation_id", item)
            for item in self.affected_invocation_ids
        )
        prefix = (
            f"{LayoutAnnotationModelInvocationResult.CONTRACT_NAME}:sha256:"
        )
        if any(
            not item.startswith(prefix)
            or not SHA256Hash.is_canonical(item.removeprefix(prefix))
            for item in affected
        ):
            raise ValueError("affected invocation identity is invalid")
        if len(set(affected)) != len(affected):
            raise ValueError("affected invocation IDs must be unique")
        object.__setattr__(
            self,
            "limitation_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                case,
                self.code,
                affected,
            ),
        )
