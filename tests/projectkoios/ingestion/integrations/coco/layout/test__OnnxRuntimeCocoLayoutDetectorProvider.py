"""Verified ONNX local-detector provider boundary tests."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.artifact.managed.verification.error import (
    ManagedArtifactVerificationError,
)
from projectkoios.ingestion.artifact.managed.verification.provider import (
    ManagedArtifactByteProvider,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.onnx import (  # noqa: E501
    MAX_INVOCATION_STREAM_CHUNK_BYTES,
    create_coco_layout_detector_observations,
    read_verified_coco_layout_detector_image_bytes,
    read_verified_coco_layout_detector_model_bytes,
    validate_coco_layout_detector_onnx_outputs,
    validate_heron_onnx_preprocessing,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.preprocessing import (  # noqa: E501
    CocoLayoutDetectorPreprocessing,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.provider import (  # noqa: E501
    CocoLayoutDetectorProviderError,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.result import (  # noqa: E501
    CocoLayoutDetectorInvocationFailureKind,
)
from projectkoios.ingestion.integrations.coco.layout.detector.resource import (
    MAX_COCO_LAYOUT_DETECTOR_MODEL_BYTES,
    CocoLayoutDetectorResource,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_invocation_request,
)


@contextmanager
def oversized_chunks_context() -> Iterator[Iterator[bytes]]:
    """Open one deliberately oversized provider chunk."""
    yield iter((b"x" * (MAX_INVOCATION_STREAM_CHUNK_BYTES + 1),))


@contextmanager
def managed_entry_failure_context() -> Iterator[Iterator[bytes]]:
    """Fail while entering the managed byte stream."""
    raise ManagedArtifactVerificationError(
        code="artifact_unavailable",
        message="fixture entry failure",
    )
    yield iter(())  # pragma: no cover - required by contextmanager typing


@contextmanager
def managed_iteration_failure_context(
    cleanup_state: list[bool],
) -> Iterator[Iterator[bytes]]:
    """Fail while iterating the managed byte stream, then record cleanup."""

    def chunks() -> Iterator[bytes]:
        raise ManagedArtifactVerificationError(
            code="artifact_byte_limit_exceeded",
            message="fixture iteration failure",
        )
        yield b""  # pragma: no cover - required by generator typing

    try:
        yield chunks()
    finally:
        cleanup_state[0] = True


class FixtureTensor:
    """Expose only the array metadata and indexing used at the boundary."""

    def __init__(
        self, *, shape: tuple[int, ...], dtype: str, rows: list[object]
    ) -> None:
        self.shape = shape
        self.dtype = dtype
        self.rows = rows

    def __getitem__(self, index: int) -> object:
        return self.rows[index]


class ManagedFailureProvider(ManagedArtifactByteProvider):
    """Raise one typed managed-byte failure at a configured stage."""

    def __init__(self, *, stage: str) -> None:
        self.stage = stage
        self.cleanup_state = [False]

    @property
    def cleaned_up(self) -> bool:
        return self.cleanup_state[0]

    @property
    def implementation_id(self) -> str:
        return "managed-failure-provider:1"

    def open_chunks(
        self,
        *,
        reference: ManagedArtifactReference,
        authority_id: str,
        maximum_bytes: int,
        chunk_bytes: int,
    ) -> AbstractContextManager[Iterator[bytes]]:
        del reference, authority_id, maximum_bytes, chunk_bytes
        if self.stage == "entry":
            return managed_entry_failure_context()
        return managed_iteration_failure_context(self.cleanup_state)


class OversizedChunkProvider(ManagedArtifactByteProvider):
    """Yield one chunk larger than the invocation stream limit."""

    @property
    def implementation_id(self) -> str:
        return "oversized-chunk-provider:1"

    def open_chunks(
        self,
        *,
        reference: ManagedArtifactReference,
        authority_id: str,
        maximum_bytes: int,
        chunk_bytes: int,
    ) -> AbstractContextManager[Iterator[bytes]]:
        del reference, authority_id, maximum_bytes, chunk_bytes
        return oversized_chunks_context()


def valid_output_tensors() -> list[FixtureTensor]:
    """Return protocol-valid synthetic Heron output tensors."""
    return [
        FixtureTensor(shape=(1, 2), dtype="int64", rows=[[1, 2]]),
        FixtureTensor(
            shape=(1, 2, 4),
            dtype="float32",
            rows=[[[1.0, 1.0, 2.0, 2.0], [3.0, 3.0, 4.0, 4.0]]],
        ),
        FixtureTensor(shape=(1, 2), dtype="float32", rows=[[0.9, 0.8]]),
    ]


def fixture_resource(content: bytes) -> CocoLayoutDetectorResource:
    """Bind one temporary exact model resource."""
    return CocoLayoutDetectorResource(
        resource_identity="fixture:model",
        source_revision="fixture-revision",
        artifact_name="model.onnx",
        artifact_sha256=SHA256Hash(
            SHA256Fingerprinter.fingerprint(content=content)
        ),
        artifact_byte_length=len(content),
        license_identity="fixture-license",
    )


@pytest.mark.parametrize(
    ("output_index", "shape", "dtype", "expected_code"),
    (
        (0, (2,), "int64", "output_tensor_shape_invalid"),
        (0, (2, 2), "int64", "output_tensor_shape_invalid"),
        (1, (1, 2), "float32", "output_tensor_shape_invalid"),
        (1, (1, 2, 5), "float32", "output_tensor_shape_invalid"),
        (2, (1, 3), "float32", "output_tensor_shape_invalid"),
        (0, (1, 2), "int32", "output_tensor_dtype_invalid"),
        (1, (1, 2, 4), "float64", "output_tensor_dtype_invalid"),
        (2, (1, 2), "float64", "output_tensor_dtype_invalid"),
    ),
)
def test_onnx_output_validation_rejects_malformed_tensor_contract(
    output_index: int,
    shape: tuple[int, ...],
    dtype: str,
    expected_code: str,
) -> None:
    outputs = valid_output_tensors()
    original = outputs[output_index]
    outputs[output_index] = FixtureTensor(
        shape=shape,
        dtype=dtype,
        rows=original.rows,
    )

    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        validate_coco_layout_detector_onnx_outputs(
            outputs=outputs,
            maximum_observations=300,
        )

    assert raised.value.kind is (
        CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL
    )
    assert raised.value.code == expected_code


@pytest.mark.parametrize("outputs", ([], valid_output_tensors()[:2]))
def test_onnx_output_validation_rejects_wrong_output_count(
    outputs: list[FixtureTensor],
) -> None:
    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        validate_coco_layout_detector_onnx_outputs(
            outputs=outputs,
            maximum_observations=300,
        )

    assert raised.value.kind is (
        CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL
    )
    assert raised.value.code == "unexpected_output_count"


def test_onnx_output_validation_classifies_count_overflow_separately() -> None:
    outputs = valid_output_tensors()

    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        validate_coco_layout_detector_onnx_outputs(
            outputs=outputs,
            maximum_observations=1,
        )

    assert raised.value.kind is (
        CocoLayoutDetectorInvocationFailureKind.OUTPUT_LIMIT
    )
    assert raised.value.code == "observation_count_exceeded"


@pytest.mark.parametrize(
    ("labels", "boxes", "scores"),
    (
        ([1.5], [[1.0, 1.0, 2.0, 2.0]], [0.9]),
        ([float("nan")], [[1.0, 1.0, 2.0, 2.0]], [0.9]),
        ([1], [[1.0, 1.0, float("inf"), 2.0]], [0.9]),
        ([1], [[1.0, 1.0, 2.0, 2.0]], [float("nan")]),
    ),
)
def test_onnx_observation_construction_rejects_nonfinite_values(
    labels: list[float | int],
    boxes: list[list[float]],
    scores: list[float],
) -> None:
    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        create_coco_layout_detector_observations(
            render_id=coco_layout_invocation_request().render.render_id,
            labels=labels,
            boxes=boxes,
            scores=scores,
        )

    assert raised.value.kind is (
        CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL
    )
    assert raised.value.code == "observation_values_invalid"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("target_width", 641),
        ("target_height", 639),
        ("target_width", 16_384),
    ),
)
def test_heron_preprocessing_rejects_non_640_target(
    field: str, value: int
) -> None:
    exact = CocoLayoutDetectorPreprocessing.docling_heron_onnx_v0_1()
    preprocessing = (
        replace(exact, target_width=value)
        if field == "target_width"
        else replace(exact, target_height=value)
    )

    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        validate_heron_onnx_preprocessing(preprocessing)

    assert raised.value.kind is (
        CocoLayoutDetectorInvocationFailureKind.REQUEST_LIMIT
    )
    assert raised.value.code == "unsupported_preprocessing_configuration"


def test_model_resource_accepts_declared_bytes_at_hard_ceiling() -> None:
    resource = CocoLayoutDetectorResource(
        resource_identity="fixture:model",
        source_revision="fixture-revision",
        artifact_name="model.onnx",
        artifact_sha256=SHA256Hash("a" * 64),
        artifact_byte_length=MAX_COCO_LAYOUT_DETECTOR_MODEL_BYTES,
        license_identity="fixture-license",
    )

    assert resource.artifact_byte_length == MAX_COCO_LAYOUT_DETECTOR_MODEL_BYTES


def test_model_resource_rejects_declared_bytes_above_hard_ceiling() -> None:
    with pytest.raises(ValueError, match="artifact_byte_length exceeds"):
        CocoLayoutDetectorResource(
            resource_identity="fixture:model",
            source_revision="fixture-revision",
            artifact_name="model.onnx",
            artifact_sha256=SHA256Hash("a" * 64),
            artifact_byte_length=(MAX_COCO_LAYOUT_DETECTOR_MODEL_BYTES + 1),
            license_identity="fixture-license",
        )


def test_model_reader_verifies_exact_regular_file_bytes(tmp_path: Path) -> None:
    content = b"fixture-onnx-model"
    path = tmp_path / "model.onnx"
    path.write_bytes(content)

    assert (
        read_verified_coco_layout_detector_model_bytes(
            path=path,
            resource=fixture_resource(content),
        )
        == content
    )


@pytest.mark.parametrize("mutation", (b"short", b"fixture-onnx-model-drift"))
def test_model_reader_rejects_resource_drift(
    tmp_path: Path, mutation: bytes
) -> None:
    expected = b"fixture-onnx-model"
    path = tmp_path / "model.onnx"
    path.write_bytes(mutation)

    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        read_verified_coco_layout_detector_model_bytes(
            path=path,
            resource=fixture_resource(expected),
        )

    assert raised.value.kind is (
        CocoLayoutDetectorInvocationFailureKind.RESOURCE_MISMATCH
    )
    assert raised.value.code == "model_bytes_differ"


@pytest.mark.parametrize(
    ("stage", "expected_kind", "expected_code"),
    (
        (
            "entry",
            CocoLayoutDetectorInvocationFailureKind.IMAGE_UNAVAILABLE,
            "managed_image_artifact_unavailable",
        ),
        (
            "iteration",
            CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH,
            "managed_image_artifact_byte_limit_exceeded",
        ),
    ),
)
def test_image_reader_maps_managed_provider_failures(
    stage: str,
    expected_kind: CocoLayoutDetectorInvocationFailureKind,
    expected_code: str,
) -> None:
    provider = ManagedFailureProvider(stage=stage)
    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        read_verified_coco_layout_detector_image_bytes(
            request=coco_layout_invocation_request(),
            provider=provider,
            authority_id="fixture-authority",
        )

    assert raised.value.kind is expected_kind
    assert raised.value.code == expected_code
    assert provider.cleaned_up is (stage == "iteration")


def test_image_reader_rejects_provider_chunk_above_bound() -> None:
    request = coco_layout_invocation_request()
    request = replace(
        request,
        image_reference=ManagedArtifactReference(
            sha256=request.image_reference.sha256,
            byte_length=MAX_INVOCATION_STREAM_CHUNK_BYTES + 1,
            media_type=request.image_reference.media_type,
        ),
    )

    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        read_verified_coco_layout_detector_image_bytes(
            request=request,
            provider=OversizedChunkProvider(),
            authority_id="fixture-authority",
        )

    assert raised.value.kind is (
        CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH
    )
    assert raised.value.code == "image_provider_chunk_invalid"


def test_model_reader_rejects_symbolic_link(tmp_path: Path) -> None:
    content = b"fixture-onnx-model"
    target = tmp_path / "target.onnx"
    target.write_bytes(content)
    link = tmp_path / "model.onnx"
    link.symlink_to(target)

    with pytest.raises(CocoLayoutDetectorProviderError) as raised:
        read_verified_coco_layout_detector_model_bytes(
            path=link,
            resource=fixture_resource(content),
        )

    assert raised.value.code == "model_path_unsafe_or_absent"
