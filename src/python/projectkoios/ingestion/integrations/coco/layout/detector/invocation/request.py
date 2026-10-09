"""Immutable exact local detector invocation requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detector.configuration import (  # noqa: E501
    CocoLayoutDetectorConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.preprocessing import (  # noqa: E501
    CocoLayoutDetectorPreprocessing,
)
from projectkoios.ingestion.integrations.coco.layout.image import (
    CocoLayoutImage,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

MAX_COCO_LAYOUT_DETECTOR_OUTPUT_BYTES = 4_000_000


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorInvocationRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Bind exact image/model/runtime inputs and hard output bounds."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-detector-invocation-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    render: LayoutPageRenderEvidence
    image: CocoLayoutImage
    image_reference: ManagedArtifactReference
    configuration: CocoLayoutDetectorConfiguration
    preprocessing: CocoLayoutDetectorPreprocessing
    provider_implementation_id: str
    execution_provider: str
    execution_device_identity: str
    maximum_output_bytes: int
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.render) is not LayoutPageRenderEvidence:
            raise TypeError("render must be LayoutPageRenderEvidence")
        if type(self.image) is not CocoLayoutImage:
            raise TypeError("image must be CocoLayoutImage")
        if type(self.image_reference) is not ManagedArtifactReference:
            raise TypeError("image_reference must be ManagedArtifactReference")
        if type(self.configuration) is not CocoLayoutDetectorConfiguration:
            raise TypeError(
                "configuration must be CocoLayoutDetectorConfiguration"
            )
        if type(self.preprocessing) is not CocoLayoutDetectorPreprocessing:
            raise TypeError(
                "preprocessing must be CocoLayoutDetectorPreprocessing"
            )
        provider = LayoutValueValidation.require_text(
            "provider_implementation_id", self.provider_implementation_id
        )
        execution_provider = LayoutValueValidation.require_text(
            "execution_provider", self.execution_provider
        )
        device = LayoutValueValidation.require_text(
            "execution_device_identity", self.execution_device_identity
        )
        maximum = LayoutValueValidation.require_positive_integer(
            "maximum_output_bytes",
            self.maximum_output_bytes,
            maximum=MAX_COCO_LAYOUT_DETECTOR_OUTPUT_BYTES,
        )
        if (
            self.image.render_id != self.render.render_id
            or self.image.width != self.render.image_width
            or self.image.height != self.render.image_height
            or self.image.image_sha256 != self.render.image_sha256
            or self.image.image_media_type != self.render.image_media_type
        ):
            raise ValueError("invocation image differs from the page render")
        # Managed references remain locator-free, but their exact bytes must be
        # the same image bytes already bound by render and COCO image evidence.
        if (
            self.image_reference.sha256 != self.image.image_sha256
            or self.image_reference.media_type.value
            != self.image.image_media_type
        ):
            raise ValueError("image reference differs from the detector image")
        object.__setattr__(self, "provider_implementation_id", provider)
        object.__setattr__(self, "execution_provider", execution_provider)
        object.__setattr__(self, "execution_device_identity", device)
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.render.render_id,
                self.image.image_identity,
                self.image_reference.artifact_id,
                self.configuration.configuration_id,
                self.preprocessing.preprocessing_id,
                provider,
                execution_provider,
                device,
                maximum,
            ),
        )

    def document_bytes(self) -> bytes:
        """Return the exact canonical non-media invocation document."""
        resource = self.configuration.resource
        return CanonicalJsonSerializer.serialize_bytes(
            {
                "contract_name": self.CONTRACT_NAME,
                "contract_version": self.CONTRACT_VERSION,
                "request_id": self.request_id,
                "render_id": self.render.render_id,
                "image": {
                    "image_identity": self.image.image_identity,
                    "artifact_id": self.image_reference.artifact_id,
                    "sha256": self.image_reference.sha256,
                    "byte_length": self.image_reference.byte_length,
                    "media_type": self.image_reference.media_type,
                    "width": self.image.width,
                    "height": self.image.height,
                },
                "configuration": {
                    "configuration_id": self.configuration.configuration_id,
                    "profile_id": self.configuration.profile.profile_id,
                    "label_mapping_inventory_id": (
                        self.configuration.label_mappings.inventory_id
                    ),
                    "minimum_confidence": (
                        self.configuration.minimum_confidence
                    ),
                    "maximum_observations": (
                        self.configuration.maximum_observations
                    ),
                    "runtime_name": self.configuration.runtime_name,
                    "runtime_version": self.configuration.runtime_version,
                },
                "resource": {
                    "resource_id": resource.resource_id,
                    "resource_identity": resource.resource_identity,
                    "source_revision": resource.source_revision,
                    "artifact_name": resource.artifact_name,
                    "artifact_sha256": resource.artifact_sha256,
                    "artifact_byte_length": resource.artifact_byte_length,
                    "license_identity": resource.license_identity,
                },
                "preprocessing": {
                    "preprocessing_id": self.preprocessing.preprocessing_id,
                    "target_width": self.preprocessing.target_width,
                    "target_height": self.preprocessing.target_height,
                    "image_mode": self.preprocessing.image_mode,
                    "resampling": self.preprocessing.resampling,
                    "tensor_data_type": self.preprocessing.tensor_data_type,
                    "tensor_layout": self.preprocessing.tensor_layout,
                    "original_size_order": (
                        self.preprocessing.original_size_order
                    ),
                },
                "provider_implementation_id": self.provider_implementation_id,
                "execution_provider": self.execution_provider,
                "execution_device_identity": self.execution_device_identity,
                "maximum_output_bytes": self.maximum_output_bytes,
            }
        )
