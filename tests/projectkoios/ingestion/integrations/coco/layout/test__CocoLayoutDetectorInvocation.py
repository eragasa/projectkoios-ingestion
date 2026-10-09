"""Exact local detector invocation evidence tests."""

import pytest
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.actionizer import (  # noqa: E501
    CocoLayoutDetectorInvocationActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.provider import (  # noqa: E501
    CocoLayoutDetectorInvocationProvider,
    CocoLayoutDetectorProviderError,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.request import (  # noqa: E501
    CocoLayoutDetectorInvocationRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.result import (  # noqa: E501
    CocoLayoutDetectorInvocationFailureKind,
    CocoLayoutDetectorInvocationResult,
    CocoLayoutDetectorInvocationStatus,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_invocation_request,
)


class FixtureDetectorProvider(CocoLayoutDetectorInvocationProvider):
    """Return one configured output or typed failure."""

    def __init__(
        self,
        *,
        output: bytes = b"{}",
        error: CocoLayoutDetectorProviderError | None = None,
        implementation_id: str = "fixture-detector-provider:1.0",
    ) -> None:
        self.output = output
        self.error = error
        self._implementation_id = implementation_id

    @property
    def implementation_id(self) -> str:
        return self._implementation_id

    def invoke(self, *, request: CocoLayoutDetectorInvocationRequest) -> bytes:
        if self.error is not None:
            raise self.error
        return self.output


def test_invocation_request_has_canonical_reconstructable_document() -> None:
    request = coco_layout_invocation_request()

    assert request == coco_layout_invocation_request()
    assert (
        request.document_bytes()
        == coco_layout_invocation_request().document_bytes()
    )
    assert request.request_id == coco_layout_invocation_request().request_id


def test_complete_invocation_retains_exact_request_and_output_bytes() -> None:
    request = coco_layout_invocation_request()
    raw_output = (
        b'{"detections":[],"render_id":"fixture","schema_version":"0.1"}'
    )
    result = CocoLayoutDetectorInvocationResult(
        request=request,
        status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        request_document_bytes=request.document_bytes(),
        raw_output_bytes=raw_output,
        elapsed_nanoseconds=123_456,
        failure_kind=None,
        failure_code=None,
    )

    assert result.request_document_sha256 == SHA256Hash(
        SHA256Fingerprinter.fingerprint(content=request.document_bytes())
    )
    assert result.raw_output_sha256 == SHA256Hash(
        SHA256Fingerprinter.fingerprint(content=raw_output)
    )
    assert result.raw_output_byte_length == len(raw_output)
    assert result == CocoLayoutDetectorInvocationResult(
        request=request,
        status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        request_document_bytes=request.document_bytes(),
        raw_output_bytes=raw_output,
        elapsed_nanoseconds=123_456,
        failure_kind=None,
        failure_code=None,
    )


@pytest.mark.parametrize(
    (
        "status",
        "raw_output",
        "failure_kind",
        "failure_code",
        "expected_message",
    ),
    (
        (
            CocoLayoutDetectorInvocationStatus.COMPLETE,
            None,
            None,
            None,
            "requires raw output",
        ),
        (
            CocoLayoutDetectorInvocationStatus.COMPLETE,
            b"{}",
            CocoLayoutDetectorInvocationFailureKind.RUNTIME,
            "runtime-failed",
            "cannot carry a failure",
        ),
        (
            CocoLayoutDetectorInvocationStatus.FAILED,
            None,
            None,
            "runtime-failed",
            "requires a failure kind",
        ),
        (
            CocoLayoutDetectorInvocationStatus.FAILED,
            b"{}",
            CocoLayoutDetectorInvocationFailureKind.RUNTIME,
            "runtime-failed",
            "cannot carry raw output",
        ),
    ),
)
def test_invocation_rejects_inconsistent_outcomes(
    status: CocoLayoutDetectorInvocationStatus,
    raw_output: bytes | None,
    failure_kind: CocoLayoutDetectorInvocationFailureKind | None,
    failure_code: str | None,
    expected_message: str,
) -> None:
    request = coco_layout_invocation_request()

    with pytest.raises(ValueError, match=expected_message):
        CocoLayoutDetectorInvocationResult(
            request=request,
            status=status,
            request_document_bytes=request.document_bytes(),
            raw_output_bytes=raw_output,
            elapsed_nanoseconds=1,
            failure_kind=failure_kind,
            failure_code=failure_code,
        )


def test_invocation_rejects_forged_request_document() -> None:
    request = coco_layout_invocation_request()

    with pytest.raises(ValueError, match="differs from request"):
        CocoLayoutDetectorInvocationResult(
            request=request,
            status=CocoLayoutDetectorInvocationStatus.FAILED,
            request_document_bytes=request.document_bytes() + b" ",
            raw_output_bytes=None,
            elapsed_nanoseconds=1,
            failure_kind=(
                CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL
            ),
            failure_code="forged-request",
        )


def test_invocation_actionizer_retains_complete_provider_output() -> None:
    request = coco_layout_invocation_request()
    result = CocoLayoutDetectorInvocationActionizer(
        provider=FixtureDetectorProvider(output=b'{"observations":[]}')
    ).action(request=request)

    assert result.status is CocoLayoutDetectorInvocationStatus.COMPLETE
    assert result.raw_output_bytes == b'{"observations":[]}'
    assert result.elapsed_nanoseconds >= 0


@pytest.mark.parametrize(
    ("provider", "expected_kind", "expected_code"),
    (
        (
            FixtureDetectorProvider(
                error=CocoLayoutDetectorProviderError(
                    kind=CocoLayoutDetectorInvocationFailureKind.RUNTIME,
                    code="runtime-failed",
                )
            ),
            CocoLayoutDetectorInvocationFailureKind.RUNTIME,
            "runtime-failed",
        ),
        (
            FixtureDetectorProvider(implementation_id="another-provider:1"),
            CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            "provider_implementation_differs",
        ),
        (
            FixtureDetectorProvider(output=b"x" * 10_001),
            CocoLayoutDetectorInvocationFailureKind.OUTPUT_LIMIT,
            "provider_output_limit_exceeded",
        ),
        (
            FixtureDetectorProvider(output=b""),
            CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            "provider_output_empty",
        ),
    ),
)
def test_invocation_actionizer_freezes_typed_failures(
    provider: CocoLayoutDetectorInvocationProvider,
    expected_kind: CocoLayoutDetectorInvocationFailureKind,
    expected_code: str,
) -> None:
    result = CocoLayoutDetectorInvocationActionizer(provider=provider).action(
        request=coco_layout_invocation_request()
    )

    assert result.status is CocoLayoutDetectorInvocationStatus.FAILED
    assert result.failure_kind is expected_kind
    assert result.failure_code == expected_code
    assert result.raw_output_bytes is None


def test_invocation_request_rejects_stale_image_reference() -> None:
    request = coco_layout_invocation_request()

    with pytest.raises(ValueError, match="reference differs"):
        CocoLayoutDetectorInvocationRequest(
            render=request.render,
            image=request.image,
            image_reference=ManagedArtifactReference(
                sha256=SHA256Hash("f" * 64),
                byte_length=123,
                media_type=request.image_reference.media_type,
            ),
            configuration=request.configuration,
            preprocessing=request.preprocessing,
            provider_implementation_id=request.provider_implementation_id,
            execution_provider=request.execution_provider,
            execution_device_identity=request.execution_device_identity,
            maximum_output_bytes=request.maximum_output_bytes,
        )
