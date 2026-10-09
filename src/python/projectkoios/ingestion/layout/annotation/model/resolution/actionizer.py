"""Pure replicated model-annotation resolution."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.layout.annotation.model.limitation import (
    LayoutModelAnnotationLimitation,
    LayoutModelAnnotationLimitationCode,
)
from projectkoios.ingestion.layout.annotation.model.parsing.status import (
    LayoutModelResponseParsingStatus,
)
from projectkoios.ingestion.layout.annotation.model.resolution.request import (
    LayoutModelAnnotationResolutionRequest,
)
from projectkoios.ingestion.layout.annotation.model.resolution.result import (
    LayoutModelAnnotationResolutionResult,
    LayoutModelAnnotationResolutionStatus,
)


class LayoutModelAnnotationResolutionActionizer(
    DataObjectActionizer[
        LayoutModelAnnotationResolutionRequest,
        LayoutModelAnnotationResolutionResult,
    ]
):
    """Admit only replicated, structurally valid, non-conflicting evidence."""

    def action(
        self, *, request: LayoutModelAnnotationResolutionRequest
    ) -> LayoutModelAnnotationResolutionResult:
        """Resolve one complete replica set without external side effects."""
        if type(request) is not LayoutModelAnnotationResolutionRequest:
            raise TypeError(
                "request must be LayoutModelAnnotationResolutionRequest"
            )
        parsed = tuple(
            item
            for item in request.parsing_results
            if item.status is LayoutModelResponseParsingStatus.PARSED
        )
        if len(parsed) < request.policy.minimum_agreement_count:
            return self.unresolved(
                request,
                LayoutModelAnnotationLimitationCode.INSUFFICIENT_VALID_RESPONSES,
            )
        candidate_ids = {
            item.candidate.candidate_id
            for item in parsed
            if item.candidate is not None
        }
        if len(candidate_ids) != 1:
            return self.unresolved(
                request,
                LayoutModelAnnotationLimitationCode.CONFLICTING_VALID_RESPONSES,
            )
        candidate = parsed[0].candidate
        if candidate is None:
            raise RuntimeError("parsed result omitted its candidate")
        agreeing_ids = tuple(item.invocation_id for item in parsed)
        return LayoutModelAnnotationResolutionResult(
            request=request,
            status=LayoutModelAnnotationResolutionStatus.ADMITTED,
            candidate=candidate,
            agreeing_invocation_ids=agreeing_ids,
            limitation=None,
        )

    @staticmethod
    def unresolved(
        request: LayoutModelAnnotationResolutionRequest,
        code: LayoutModelAnnotationLimitationCode,
    ) -> LayoutModelAnnotationResolutionResult:
        """Create one explicit unresolved result over the full replica set."""
        limitation = LayoutModelAnnotationLimitation(
            case_id=request.case.case_id,
            code=code,
            affected_invocation_ids=tuple(
                item.invocation_id for item in request.parsing_results
            ),
        )
        return LayoutModelAnnotationResolutionResult(
            request=request,
            status=LayoutModelAnnotationResolutionStatus.UNRESOLVED,
            candidate=None,
            agreeing_invocation_ids=(),
            limitation=limitation,
        )
