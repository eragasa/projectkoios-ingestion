"""Effectful bounded local detector invocation actionizer."""

from __future__ import annotations

from time import monotonic_ns

from projectkoios.base import DataObjectActionizer

from .provider import (
    CocoLayoutDetectorInvocationProvider,
    CocoLayoutDetectorProviderError,
)
from .request import CocoLayoutDetectorInvocationRequest
from .result import (
    CocoLayoutDetectorInvocationFailureKind,
    CocoLayoutDetectorInvocationResult,
    CocoLayoutDetectorInvocationStatus,
)


class CocoLayoutDetectorInvocationActionizer(
    DataObjectActionizer[
        CocoLayoutDetectorInvocationRequest,
        CocoLayoutDetectorInvocationResult,
    ]
):
    """Execute one exact request and retain bounded raw invocation evidence."""

    __slots__ = ("provider",)

    def __init__(
        self, *, provider: CocoLayoutDetectorInvocationProvider
    ) -> None:
        if not isinstance(provider, CocoLayoutDetectorInvocationProvider):
            raise TypeError(
                "provider must be CocoLayoutDetectorInvocationProvider"
            )
        self.provider = provider

    def action(
        self, *, request: CocoLayoutDetectorInvocationRequest
    ) -> CocoLayoutDetectorInvocationResult:
        """Invoke the provider once without retries or lifecycle inference."""
        if type(request) is not CocoLayoutDetectorInvocationRequest:
            raise TypeError(
                "request must be CocoLayoutDetectorInvocationRequest"
            )
        if (
            request.provider_implementation_id
            != self.provider.implementation_id
        ):
            return create_failed_coco_layout_detector_invocation_result(
                request=request,
                started_at=monotonic_ns(),
                kind=(
                    CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL
                ),
                code="provider_implementation_differs",
            )
        started_at = monotonic_ns()
        try:
            raw_output = self.provider.invoke(request=request)
        except CocoLayoutDetectorProviderError as error:
            return create_failed_coco_layout_detector_invocation_result(
                request=request,
                started_at=started_at,
                kind=error.kind,
                code=error.code,
            )
        elapsed = max(0, monotonic_ns() - started_at)
        if type(raw_output) is not bytes:
            return CocoLayoutDetectorInvocationResult(
                request=request,
                status=CocoLayoutDetectorInvocationStatus.FAILED,
                request_document_bytes=request.document_bytes(),
                raw_output_bytes=None,
                elapsed_nanoseconds=elapsed,
                failure_kind=(
                    CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL
                ),
                failure_code="provider_output_not_bytes",
            )
        if len(raw_output) > request.maximum_output_bytes:
            return CocoLayoutDetectorInvocationResult(
                request=request,
                status=CocoLayoutDetectorInvocationStatus.FAILED,
                request_document_bytes=request.document_bytes(),
                raw_output_bytes=None,
                elapsed_nanoseconds=elapsed,
                failure_kind=(
                    CocoLayoutDetectorInvocationFailureKind.OUTPUT_LIMIT
                ),
                failure_code="provider_output_limit_exceeded",
            )
        if not raw_output:
            return CocoLayoutDetectorInvocationResult(
                request=request,
                status=CocoLayoutDetectorInvocationStatus.FAILED,
                request_document_bytes=request.document_bytes(),
                raw_output_bytes=None,
                elapsed_nanoseconds=elapsed,
                failure_kind=(
                    CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL
                ),
                failure_code="provider_output_empty",
            )
        return CocoLayoutDetectorInvocationResult(
            request=request,
            status=CocoLayoutDetectorInvocationStatus.COMPLETE,
            request_document_bytes=request.document_bytes(),
            raw_output_bytes=raw_output,
            elapsed_nanoseconds=elapsed,
            failure_kind=None,
            failure_code=None,
        )


def create_failed_coco_layout_detector_invocation_result(
    *,
    request: CocoLayoutDetectorInvocationRequest,
    started_at: int,
    kind: CocoLayoutDetectorInvocationFailureKind,
    code: str,
) -> CocoLayoutDetectorInvocationResult:
    """Freeze one typed provider failure with elapsed-time evidence."""
    return CocoLayoutDetectorInvocationResult(
        request=request,
        status=CocoLayoutDetectorInvocationStatus.FAILED,
        request_document_bytes=request.document_bytes(),
        raw_output_bytes=None,
        elapsed_nanoseconds=max(0, monotonic_ns() - started_at),
        failure_kind=kind,
        failure_code=code,
    )
