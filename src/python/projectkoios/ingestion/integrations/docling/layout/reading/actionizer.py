"""Strict Docling reading-order candidate actionizer."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.layout.reading.order.candidate import (
    LayoutReadingOrderCandidate,
    LayoutReadingOrderCandidateEvidence,
)

from .kind import DoclingReadingOrderFailureKind, DoclingReadingOrderStatus
from .provider import (
    DoclingReadingOrderProvider,
    DoclingReadingOrderProviderError,
)
from .request import DoclingReadingOrderRequest
from .result import DoclingReadingOrderResult


class DoclingReadingOrderActionizer(
    DataObjectActionizer[
        DoclingReadingOrderRequest,
        DoclingReadingOrderResult,
    ]
):
    """Invoke one provider and fail closed on any non-permutation output."""

    __slots__ = ("provider",)

    def __init__(self, *, provider: DoclingReadingOrderProvider) -> None:
        if not isinstance(provider, DoclingReadingOrderProvider):
            raise TypeError("provider must be DoclingReadingOrderProvider")
        self.provider = provider

    def action(
        self, *, request: DoclingReadingOrderRequest
    ) -> DoclingReadingOrderResult:
        """Produce one candidate without claiming semantic correctness."""
        if type(request) is not DoclingReadingOrderRequest:
            raise TypeError("request must be DoclingReadingOrderRequest")
        provider_id = self.provider.implementation_id
        if provider_id != request.configuration.provider_implementation_id:
            return self.unresolved_result(
                request=request,
                provider_id=provider_id,
                failure_kind=(
                    DoclingReadingOrderFailureKind.PROVIDER_VERSION_MISMATCH
                ),
            )
        try:
            raw_order = self.provider.order(request=request)
        except DoclingReadingOrderProviderError as error:
            return self.unresolved_result(
                request=request,
                provider_id=provider_id,
                failure_kind=error.kind,
            )
        if type(raw_order) is not tuple:
            return self.unresolved_result(
                request=request,
                provider_id=provider_id,
                failure_kind=(
                    DoclingReadingOrderFailureKind.OUTPUT_TYPE_INVALID
                ),
            )
        if len(raw_order) > request.configuration.maximum_elements:
            return self.unresolved_result(
                request=request,
                provider_id=provider_id,
                failure_kind=(
                    DoclingReadingOrderFailureKind.OUTPUT_ELEMENT_LIMIT_EXCEEDED
                ),
            )
        if any(not isinstance(element_id, str) for element_id in raw_order):
            return self.unresolved_result(
                request=request,
                provider_id=provider_id,
                failure_kind=(
                    DoclingReadingOrderFailureKind.OUTPUT_TYPE_INVALID
                ),
            )
        expected_ids = tuple(element.region_id for element in request.elements)
        if len(raw_order) != len(set(raw_order)):
            failure = DoclingReadingOrderFailureKind.OUTPUT_DUPLICATE_ELEMENT
        elif set(raw_order) - set(expected_ids):
            failure = DoclingReadingOrderFailureKind.OUTPUT_UNKNOWN_ELEMENT
        elif len(raw_order) != len(expected_ids):
            failure = DoclingReadingOrderFailureKind.OUTPUT_INCOMPLETE
        else:
            return DoclingReadingOrderResult(
                request=request,
                provider_implementation_id=provider_id,
                status=DoclingReadingOrderStatus.CANDIDATE_PRODUCED,
                candidate_evidence=LayoutReadingOrderCandidateEvidence(
                    source_request_id=request.request_id,
                    producer_implementation_id=provider_id,
                    render_id=request.render_id,
                    upstream_evidence_id=request.upstream_evidence_id,
                    direction=request.direction,
                    elements=request.elements,
                    candidate=LayoutReadingOrderCandidate(*raw_order),
                ),
                failure_kind=None,
            )
        return self.unresolved_result(
            request=request,
            provider_id=provider_id,
            failure_kind=failure,
        )

    @staticmethod
    def unresolved_result(
        *,
        request: DoclingReadingOrderRequest,
        provider_id: str,
        failure_kind: DoclingReadingOrderFailureKind,
    ) -> DoclingReadingOrderResult:
        """Create one explicit provider or output-validation failure."""
        return DoclingReadingOrderResult(
            request=request,
            provider_implementation_id=provider_id,
            status=DoclingReadingOrderStatus.UNRESOLVED,
            candidate_evidence=None,
            failure_kind=failure_kind,
        )
