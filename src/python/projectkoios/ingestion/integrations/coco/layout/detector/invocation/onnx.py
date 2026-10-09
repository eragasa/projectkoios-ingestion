"""Verified ONNX Runtime provider for the pinned Heron detector family."""

from __future__ import annotations

import math
import os
import stat
from contextlib import closing
from importlib import import_module
from io import BytesIO
from pathlib import Path
from typing import Any

from projectkoios.ingestion.artifact.managed.verification.error import (
    ManagedArtifactVerificationError,
)
from projectkoios.ingestion.artifact.managed.verification.provider import (
    ManagedArtifactByteProvider,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detector.observation import (  # noqa: E501
    CocoLayoutDetectorObservation,
    CocoLayoutDetectorObservationInventory,
)
from projectkoios.ingestion.integrations.coco.layout.detector.resource import (
    CocoLayoutDetectorResource,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

from .output import (
    CocoLayoutDetectorRawOutput,
    CocoLayoutDetectorRawOutputJsonContract,
)
from .preprocessing import CocoLayoutDetectorPreprocessing
from .provider import (
    CocoLayoutDetectorInvocationProvider,
    CocoLayoutDetectorProviderError,
)
from .request import CocoLayoutDetectorInvocationRequest
from .result import CocoLayoutDetectorInvocationFailureKind

MODEL_INPUT_NAME = "images"
ORIGINAL_SIZE_INPUT_NAME = "orig_target_sizes"
MAX_INVOCATION_STREAM_CHUNK_BYTES = 1024 * 1024
SUPPORTED_EXECUTION_PROVIDER = "CPUExecutionProvider"


class OnnxRuntimeCocoLayoutDetectorProvider(
    CocoLayoutDetectorInvocationProvider
):
    """Verify exact model/image bytes and execute bounded CPU inference."""

    __slots__ = (
        "_implementation_id",
        "authority_id",
        "execution_device_identity",
        "execution_provider",
        "image_provider",
        "model_path",
        "numpy",
        "onnxruntime",
        "pillow",
        "pillow_image",
    )

    def __init__(
        self,
        *,
        model_path: Path,
        image_provider: ManagedArtifactByteProvider,
        authority_id: str,
        execution_provider: str,
        execution_device_identity: str,
    ) -> None:
        if not isinstance(image_provider, ManagedArtifactByteProvider):
            raise TypeError(
                "image_provider must be ManagedArtifactByteProvider"
            )
        if type(model_path) is not Path:
            raise TypeError("model_path must be pathlib.Path")
        if not authority_id or not execution_provider:
            raise ValueError("authority and execution provider are required")
        if not execution_device_identity:
            raise ValueError("execution device identity is required")
        try:
            onnxruntime = import_module("onnxruntime")
            numpy = import_module("numpy")
            pillow = import_module("PIL")
            pillow_image = import_module("PIL.Image")
        except ImportError as error:
            raise RuntimeError(
                "ONNX detector optional dependencies are unavailable"
            ) from error
        self.model_path = model_path.expanduser().absolute()
        self.image_provider = image_provider
        self.authority_id = authority_id
        self.execution_provider = execution_provider
        self.execution_device_identity = execution_device_identity
        self.onnxruntime = onnxruntime
        self.numpy = numpy
        self.pillow = pillow
        self.pillow_image = pillow_image
        self._implementation_id = stable_id(
            "onnx-runtime-coco-layout-detector-provider",
            "1.0",
            getattr(onnxruntime, "__version__", "unknown"),
            getattr(numpy, "__version__", "unknown"),
            getattr(pillow, "__version__", "unknown"),
            execution_provider,
            execution_device_identity,
            image_provider.implementation_id,
        )

    @property
    def implementation_id(self) -> str:
        return self._implementation_id

    def invoke(self, *, request: CocoLayoutDetectorInvocationRequest) -> bytes:
        """Verify bytes, execute the request, and emit canonical output."""
        validate_onnx_runtime_request(
            request=request,
            provider=self,
        )
        model_bytes = read_verified_coco_layout_detector_model_bytes(
            path=self.model_path,
            resource=request.configuration.resource,
        )
        image_bytes = read_verified_coco_layout_detector_image_bytes(
            request=request,
            provider=self.image_provider,
            authority_id=self.authority_id,
        )
        try:
            observations = execute_coco_layout_detector_onnx_runtime(
                request=request,
                model_bytes=model_bytes,
                image_bytes=image_bytes,
                onnxruntime=self.onnxruntime,
                numpy=self.numpy,
                pillow_image=self.pillow_image,
            )
            output = CocoLayoutDetectorRawOutput(
                render_id=request.render.render_id,
                resource_id=request.configuration.resource.resource_id,
                preprocessing_id=request.preprocessing.preprocessing_id,
                observations=observations,
            )
            return CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(
                output
            )
        except CocoLayoutDetectorProviderError:
            raise
        except Exception as error:
            raise CocoLayoutDetectorProviderError(
                kind=CocoLayoutDetectorInvocationFailureKind.RUNTIME,
                code="onnx_runtime_execution_failed",
            ) from error


def validate_onnx_runtime_request(
    *,
    request: CocoLayoutDetectorInvocationRequest,
    provider: OnnxRuntimeCocoLayoutDetectorProvider,
) -> None:
    """Require request/runtime/preprocessing identity agreement."""
    validate_heron_onnx_preprocessing(request.preprocessing)
    if (
        request.provider_implementation_id != provider.implementation_id
        or request.execution_provider != provider.execution_provider
        or request.execution_device_identity
        != provider.execution_device_identity
    ):
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            code="runtime_identity_differs",
        )
    if (
        request.configuration.runtime_name != "onnxruntime"
        or request.configuration.runtime_version
        != getattr(provider.onnxruntime, "__version__", "unknown")
    ):
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.RESOURCE_MISMATCH,
            code="onnx_runtime_version_differs",
        )
    if provider.execution_provider != SUPPORTED_EXECUTION_PROVIDER:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.REQUEST_LIMIT,
            code="execution_provider_unsupported",
        )
    available = provider.onnxruntime.get_available_providers()
    if provider.execution_provider not in available:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.RUNTIME,
            code="execution_provider_unavailable",
        )


def validate_heron_onnx_preprocessing(preprocessing: object) -> None:
    """Require the exact preprocessing identity pinned for Heron v0.1."""
    expected = CocoLayoutDetectorPreprocessing.docling_heron_onnx_v0_1()
    if preprocessing != expected:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.REQUEST_LIMIT,
            code="unsupported_preprocessing_configuration",
        )


def read_verified_coco_layout_detector_model_bytes(
    *, path: Path, resource: CocoLayoutDetectorResource
) -> bytes:
    """Read exact immutable model bytes without retaining their locator."""
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("model resource is not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            content = stream.read(resource.artifact_byte_length + 1)
    except OSError as error:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.RESOURCE_MISMATCH,
            code="model_path_unsafe_or_absent",
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (
        len(content) != resource.artifact_byte_length
        or SHA256Fingerprinter.fingerprint(content=content)
        != resource.artifact_sha256
    ):
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.RESOURCE_MISMATCH,
            code="model_bytes_differ",
        )
    return content


def read_verified_coco_layout_detector_image_bytes(
    *,
    request: CocoLayoutDetectorInvocationRequest,
    provider: ManagedArtifactByteProvider,
    authority_id: str,
) -> bytes:
    """Resolve and verify bounded image bytes for one invocation only."""
    reference = request.image_reference
    chunks: list[bytes] = []
    observed_length = 0
    try:
        with provider.open_chunks(
            reference=reference,
            authority_id=authority_id,
            maximum_bytes=reference.byte_length,
            chunk_bytes=min(
                reference.byte_length,
                MAX_INVOCATION_STREAM_CHUNK_BYTES,
            ),
        ) as stream:
            for chunk in stream:
                if (
                    type(chunk) is not bytes
                    or not chunk
                    or len(chunk) > MAX_INVOCATION_STREAM_CHUNK_BYTES
                ):
                    raise CocoLayoutDetectorProviderError(
                        kind=(
                            CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH
                        ),
                        code="image_provider_chunk_invalid",
                    )
                observed_length += len(chunk)
                if observed_length > reference.byte_length:
                    raise CocoLayoutDetectorProviderError(
                        kind=(
                            CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH
                        ),
                        code="image_provider_length_exceeded",
                    )
                chunks.append(chunk)
    except CocoLayoutDetectorProviderError:
        raise
    except ManagedArtifactVerificationError as error:
        raise map_managed_image_provider_error(error) from error
    except Exception as error:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.IMAGE_UNAVAILABLE,
            code="image_provider_failed",
        ) from error
    content = b"".join(chunks)
    if (
        len(content) != reference.byte_length
        or SHA256Fingerprinter.fingerprint(content=content) != reference.sha256
    ):
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH,
            code="image_bytes_differ",
        )
    return content


def map_managed_image_provider_error(
    error: ManagedArtifactVerificationError,
) -> CocoLayoutDetectorProviderError:
    """Map managed-byte failures into the closed detector taxonomy."""
    mismatch_codes = {
        "artifact_byte_limit_exceeded",
        "artifact_bytes_differ",
    }
    kind = (
        CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH
        if error.code in mismatch_codes
        else CocoLayoutDetectorInvocationFailureKind.IMAGE_UNAVAILABLE
    )
    return CocoLayoutDetectorProviderError(
        kind=kind,
        code=f"managed_image_{error.code}",
    )


def execute_coco_layout_detector_onnx_runtime(
    *,
    request: CocoLayoutDetectorInvocationRequest,
    model_bytes: bytes,
    image_bytes: bytes,
    onnxruntime: Any,
    numpy: Any,
    pillow_image: Any,
) -> CocoLayoutDetectorObservationInventory:
    """Execute Heron-compatible ONNX tensors and freeze neutral observations."""
    try:
        with closing(pillow_image.open(BytesIO(image_bytes))) as image:
            image.load()
            if image.size != (request.image.width, request.image.height):
                raise CocoLayoutDetectorProviderError(
                    kind=CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH,
                    code="decoded_image_dimensions_differ",
                )
            with closing(
                image.convert(request.preprocessing.image_mode.value)
            ) as converted:
                with closing(
                    converted.resize(
                        (
                            request.preprocessing.target_width,
                            request.preprocessing.target_height,
                        ),
                        resample=pillow_image.Resampling.BILINEAR,
                    )
                ) as resized:
                    tensor = numpy.asarray(
                        resized, dtype=numpy.uint8
                    ).transpose(2, 0, 1)[None, ...]
    except CocoLayoutDetectorProviderError:
        raise
    except Exception as error:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.IMAGE_MISMATCH,
            code="image_decode_or_preprocessing_failed",
        ) from error
    original_sizes = numpy.asarray(
        [[request.image.height, request.image.width]], dtype=numpy.int64
    )
    session = onnxruntime.InferenceSession(
        model_bytes,
        providers=[request.execution_provider],
    )
    if session.get_providers() != [SUPPORTED_EXECUTION_PROVIDER]:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.RUNTIME,
            code="execution_provider_activation_differs",
        )
    outputs = session.run(
        None,
        {
            MODEL_INPUT_NAME: tensor,
            ORIGINAL_SIZE_INPUT_NAME: original_sizes,
        },
    )
    labels, boxes, scores = validate_coco_layout_detector_onnx_outputs(
        outputs=outputs,
        maximum_observations=request.configuration.maximum_observations,
    )
    return create_coco_layout_detector_observations(
        render_id=request.render.render_id,
        labels=labels,
        boxes=boxes,
        scores=scores,
    )


def create_coco_layout_detector_observations(
    *, render_id: str, labels: Any, boxes: Any, scores: Any
) -> CocoLayoutDetectorObservationInventory:
    """Construct observations only from finite, aligned output values."""
    observations: list[CocoLayoutDetectorObservation] = []
    try:
        for label, box, score in zip(labels, boxes, scores, strict=True):
            coordinates = tuple(float(value) for value in box)
            integer_label = int(label)
            numeric_label = float(label)
            numeric_score = float(score)
            if (
                len(coordinates) != 4
                or numeric_label != integer_label
                or not math.isfinite(numeric_label)
                or not math.isfinite(numeric_score)
                or any(
                    not math.isfinite(coordinate) for coordinate in coordinates
                )
            ):
                raise ValueError("detector observation values are invalid")
            observations.append(
                CocoLayoutDetectorObservation(
                    render_id=render_id,
                    model_label_id=integer_label,
                    bounding_box_xyxy_pixels=(
                        coordinates[0],
                        coordinates[1],
                        coordinates[2],
                        coordinates[3],
                    ),
                    confidence=numeric_score,
                )
            )
        return CocoLayoutDetectorObservationInventory(*observations)
    except (TypeError, ValueError, OverflowError) as error:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            code="observation_values_invalid",
        ) from error


def validate_coco_layout_detector_onnx_outputs(
    *, outputs: object, maximum_observations: int
) -> tuple[Any, Any, Any]:
    """Require exact Heron output ranks, shapes, dtypes, and hard count."""
    if type(outputs) is not list or len(outputs) != 3:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            code="unexpected_output_count",
        )
    labels_tensor, boxes_tensor, scores_tensor = outputs
    try:
        labels_shape = tuple(labels_tensor.shape)
        boxes_shape = tuple(boxes_tensor.shape)
        scores_shape = tuple(scores_tensor.shape)
        labels_dtype = str(labels_tensor.dtype)
        boxes_dtype = str(boxes_tensor.dtype)
        scores_dtype = str(scores_tensor.dtype)
    except (AttributeError, TypeError) as error:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            code="output_tensor_metadata_invalid",
        ) from error
    if (
        len(labels_shape) != 2
        or len(boxes_shape) != 3
        or len(scores_shape) != 2
        or labels_shape[0] != 1
        or boxes_shape[0] != 1
        or scores_shape[0] != 1
        or boxes_shape[2] != 4
        or labels_shape[1] != boxes_shape[1]
        or labels_shape[1] != scores_shape[1]
    ):
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            code="output_tensor_shape_invalid",
        )
    if (
        labels_dtype != "int64"
        or boxes_dtype != "float32"
        or scores_dtype != "float32"
    ):
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            code="output_tensor_dtype_invalid",
        )
    if labels_shape[1] > maximum_observations:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.OUTPUT_LIMIT,
            code="observation_count_exceeded",
        )
    try:
        return labels_tensor[0], boxes_tensor[0], scores_tensor[0]
    except (IndexError, TypeError) as error:
        raise CocoLayoutDetectorProviderError(
            kind=CocoLayoutDetectorInvocationFailureKind.PROVIDER_PROTOCOL,
            code="output_tensor_indexing_invalid",
        ) from error
