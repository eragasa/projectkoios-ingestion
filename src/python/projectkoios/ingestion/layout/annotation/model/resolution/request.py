"""Complete request for replicated model-annotation resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.model.parsing.result import (
    LayoutModelResponseParsingResult,
)
from projectkoios.ingestion.layout.annotation.model.resolution.policy import (
    LayoutModelAnnotationResolutionPolicy,
)
from projectkoios.ingestion.layout.review.result import LayoutReviewCase


@dataclass(frozen=True, slots=True)
class LayoutModelAnnotationResolutionRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bind one case, one policy, and the exact replica result set."""

    CONTRACT_NAME: ClassVar[str] = "layout-model-annotation-resolution-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    case: LayoutReviewCase
    policy: LayoutModelAnnotationResolutionPolicy
    parsing_results: tuple[LayoutModelResponseParsingResult, ...]
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.case) is not LayoutReviewCase:
            raise TypeError("case must be LayoutReviewCase")
        if type(self.policy) is not LayoutModelAnnotationResolutionPolicy:
            raise TypeError(
                "policy must be LayoutModelAnnotationResolutionPolicy"
            )
        if (
            not isinstance(self.parsing_results, tuple)
            or len(self.parsing_results) != self.policy.required_response_count
            or any(
                type(item) is not LayoutModelResponseParsingResult
                for item in self.parsing_results
            )
        ):
            raise ValueError(
                "parsing_results must provide the exact required result count"
            )
        replica_indexes = tuple(
            item.replica_index for item in self.parsing_results
        )
        if replica_indexes != tuple(range(self.policy.required_response_count)):
            raise ValueError(
                "parsing results must be ordered by complete replica index"
            )
        invocations = tuple(
            item.request.invocation for item in self.parsing_results
        )
        if len({item.invocation_id for item in invocations}) != len(
            invocations
        ):
            raise ValueError("model invocation identities must be unique")
        model_requests = tuple(item.request for item in invocations)
        if any(item.case != self.case for item in model_requests):
            raise ValueError("all model requests must bind the exact case")
        first = model_requests[0]
        if any(
            item.resource != first.resource
            or item.image != first.image
            or item.prompt != first.prompt
            or item.configuration != first.configuration
            for item in model_requests[1:]
        ):
            raise ValueError(
                "replicas must share model, image, prompt, and configuration"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.case.case_id,
                self.policy.policy_id,
                tuple(item.result_id for item in self.parsing_results),
            ),
        )
