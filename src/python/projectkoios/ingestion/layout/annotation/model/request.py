"""Exact provider-neutral model annotation request."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.layout.annotation.model.configuration import (
    MAX_LAYOUT_MODEL_REPLICAS,
    LayoutAnnotationModelConfiguration,
)
from projectkoios.ingestion.layout.annotation.model.prompt import (
    LayoutAnnotationModelPrompt,
)
from projectkoios.ingestion.layout.annotation.model.resource import (
    LayoutAnnotationModelResource,
)
from projectkoios.ingestion.layout.review.result import LayoutReviewCase


@dataclass(frozen=True, slots=True)
class LayoutAnnotationModelRequest(
    AbstractImmutableDataObject,
    DataObjectActionRequest,
):
    """Request one model-authored annotation over one exact review case."""

    CONTRACT_NAME: ClassVar[str] = "layout-annotation-model-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    case: LayoutReviewCase
    resource: LayoutAnnotationModelResource
    image: ManagedArtifactReference
    prompt: LayoutAnnotationModelPrompt
    configuration: LayoutAnnotationModelConfiguration
    replica_index: int
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.case) is not LayoutReviewCase:
            raise TypeError("case must be LayoutReviewCase")
        if type(self.resource) is not LayoutAnnotationModelResource:
            raise TypeError("resource must be LayoutAnnotationModelResource")
        if type(self.image) is not ManagedArtifactReference:
            raise TypeError("image must be ManagedArtifactReference")
        render = self.case.request.render
        if (
            self.image.sha256 != render.image_sha256
            or self.image.media_type.value != render.image_media_type
        ):
            raise ValueError("image reference differs from render evidence")
        if type(self.prompt) is not LayoutAnnotationModelPrompt:
            raise TypeError("prompt must be LayoutAnnotationModelPrompt")
        if self.prompt.case != self.case:
            raise ValueError("prompt is not canonical for the review case")
        if type(self.configuration) is not LayoutAnnotationModelConfiguration:
            raise TypeError(
                "configuration must be LayoutAnnotationModelConfiguration"
            )
        if (
            isinstance(self.replica_index, bool)
            or not isinstance(self.replica_index, int)
            or not 0 <= self.replica_index < MAX_LAYOUT_MODEL_REPLICAS
        ):
            raise ValueError("replica_index is outside its supported range")
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.case.case_id,
                self.resource.resource_id,
                self.image.artifact_id,
                self.prompt.prompt_id,
                self.configuration.configuration_id,
                self.replica_index,
            ),
        )

    def document_bytes(self) -> bytes:
        """Return the exact canonical non-media model request document."""
        render = self.case.request.render
        return CanonicalJsonSerializer.serialize_bytes(
            {
                "contract_name": self.CONTRACT_NAME,
                "contract_version": self.CONTRACT_VERSION,
                "request_id": self.request_id,
                "case_id": self.case.case_id,
                "resource": {
                    "resource_id": self.resource.resource_id,
                    "provider_name": self.resource.provider_name,
                    "model_name": self.resource.model_name,
                    "model_version": self.resource.model_version,
                    "model_sha256": self.resource.model_sha256,
                    "runtime_name": self.resource.runtime_name,
                    "runtime_version": self.resource.runtime_version,
                },
                "image": {
                    "artifact_id": self.image.artifact_id,
                    "sha256": self.image.sha256,
                    "byte_length": self.image.byte_length,
                    "media_type": self.image.media_type,
                },
                "prompt": {
                    "prompt_id": self.prompt.prompt_id,
                    "prompt_version": self.prompt.prompt_version,
                    "template_sha256": self.prompt.template_sha256,
                    "rendered_sha256": self.prompt.rendered_sha256,
                    "response_schema_sha256": (
                        self.prompt.response_schema_sha256
                    ),
                    "utf8_byte_length": self.prompt.utf8_byte_length,
                    "text": self.prompt.text,
                },
                "configuration": {
                    "configuration_id": self.configuration.configuration_id,
                    "temperature": self.configuration.temperature,
                    "seed": self.configuration.seed,
                    "maximum_response_bytes": (
                        self.configuration.maximum_response_bytes
                    ),
                },
                "replica_index": self.replica_index,
                "render": {
                    "render_id": render.render_id,
                    "image_media_type": render.image_media_type,
                    "image_sha256": render.image_sha256,
                    "image_width": render.image_width,
                    "image_height": render.image_height,
                },
            }
        )
