"""Resolved or explicitly unresolved model annotation evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.model.candidate import (
    LayoutModelAnnotationCandidate,
)
from projectkoios.ingestion.layout.annotation.model.limitation import (
    LayoutModelAnnotationLimitation,
    LayoutModelAnnotationLimitationCode,
)
from projectkoios.ingestion.layout.annotation.model.resolution.request import (
    LayoutModelAnnotationResolutionRequest,
)


class LayoutModelAnnotationResolutionStatus(StrEnum):
    """Closed model-evidence resolution outcome."""

    ADMITTED = "admitted"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class LayoutModelAnnotationResolutionResult(AbstractDataObjectActionResult):
    """Retain agreement admission without granting publication authority."""

    CONTRACT_NAME: ClassVar[str] = "layout-model-annotation-resolution-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    ACTIONIZER_NAME: ClassVar[str] = "layout-model-annotation-resolver"
    ACTIONIZER_VERSION: ClassVar[str] = "1.0"

    request: LayoutModelAnnotationResolutionRequest
    status: LayoutModelAnnotationResolutionStatus
    candidate: LayoutModelAnnotationCandidate | None
    agreeing_invocation_ids: tuple[str, ...]
    limitation: LayoutModelAnnotationLimitation | None
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not LayoutModelAnnotationResolutionRequest:
            raise TypeError(
                "request must be LayoutModelAnnotationResolutionRequest"
            )
        if not isinstance(self.status, LayoutModelAnnotationResolutionStatus):
            raise TypeError(
                "status must be LayoutModelAnnotationResolutionStatus"
            )
        if not isinstance(self.agreeing_invocation_ids, tuple):
            raise TypeError("agreeing_invocation_ids must be a tuple")
        available_ids = tuple(
            item.invocation_id for item in self.request.parsing_results
        )
        if len(set(self.agreeing_invocation_ids)) != len(
            self.agreeing_invocation_ids
        ) or not set(self.agreeing_invocation_ids) <= set(available_ids):
            raise ValueError("agreeing invocation IDs are invalid")
        if self.status is LayoutModelAnnotationResolutionStatus.ADMITTED:
            matching_ids = tuple(
                item.invocation_id
                for item in self.request.parsing_results
                if item.candidate is not None
                and self.candidate is not None
                and item.candidate.candidate_id == self.candidate.candidate_id
            )
            parsed_candidate_ids = {
                item.candidate.candidate_id
                for item in self.request.parsing_results
                if item.candidate is not None
            }
            if (
                type(self.candidate) is not LayoutModelAnnotationCandidate
                or self.candidate.case != self.request.case
                or self.agreeing_invocation_ids != matching_ids
                or len(self.agreeing_invocation_ids)
                < self.request.policy.minimum_agreement_count
                or len(parsed_candidate_ids) != 1
                or self.limitation is not None
            ):
                raise ValueError(
                    "admitted resolution requires sufficient exact agreement"
                )
        else:
            parsed_candidates = tuple(
                item.candidate
                for item in self.request.parsing_results
                if item.candidate is not None
            )
            candidate_ids = {item.candidate_id for item in parsed_candidates}
            limitation_codes = LayoutModelAnnotationLimitationCode
            expected_code = None
            if (
                len(parsed_candidates)
                < self.request.policy.minimum_agreement_count
            ):
                expected_code = limitation_codes.INSUFFICIENT_VALID_RESPONSES
            elif len(candidate_ids) != 1:
                expected_code = limitation_codes.CONFLICTING_VALID_RESPONSES
            if (
                self.candidate is not None
                or self.agreeing_invocation_ids
                or type(self.limitation) is not LayoutModelAnnotationLimitation
                or self.limitation.case_id != self.request.case.case_id
                or self.limitation.affected_invocation_ids != available_ids
                or self.limitation.code is not expected_code
            ):
                raise ValueError(
                    "unresolved result requires the derived full-set limitation"
                )
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.request.request_id,
                self.status,
                None if self.candidate is None else self.candidate.candidate_id,
                self.agreeing_invocation_ids,
                None
                if self.limitation is None
                else self.limitation.limitation_id,
                self.ACTIONIZER_NAME,
                self.ACTIONIZER_VERSION,
            ),
        )

    @property
    def case_id(self) -> str:
        """Return the exact review case resolved by this evidence."""
        return self.request.case.case_id
