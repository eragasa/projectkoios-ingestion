"""Exact local detector model-resource evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash

MAX_COCO_LAYOUT_DETECTOR_MODEL_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorResource(AbstractImmutableDataObject):
    """Bind exact local detector bytes without locating or authorizing them."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-detector-resource"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    resource_identity: str
    source_revision: str
    artifact_name: str
    artifact_sha256: SHA256Hash
    artifact_byte_length: int
    license_identity: str
    resource_id: str = field(init=False)

    def __post_init__(self) -> None:
        values = tuple(
            LayoutValueValidation.require_text(name, value)
            for name, value in (
                ("resource_identity", self.resource_identity),
                ("source_revision", self.source_revision),
                ("artifact_name", self.artifact_name),
                ("license_identity", self.license_identity),
            )
        )
        digest = SHA256Hash(self.artifact_sha256)
        byte_length = LayoutValueValidation.require_positive_integer(
            "artifact_byte_length",
            self.artifact_byte_length,
            maximum=MAX_COCO_LAYOUT_DETECTOR_MODEL_BYTES,
        )
        object.__setattr__(self, "resource_identity", values[0])
        object.__setattr__(self, "source_revision", values[1])
        object.__setattr__(self, "artifact_name", values[2])
        object.__setattr__(self, "artifact_sha256", digest)
        object.__setattr__(self, "license_identity", values[3])
        object.__setattr__(
            self,
            "resource_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                *values,
                digest,
                byte_length,
            ),
        )

    @classmethod
    def docling_heron_onnx_candidate(cls) -> CocoLayoutDetectorResource:
        """Return the exact pinned Heron ONNX benchmark candidate."""
        # Pin the immutable Hub revision and LFS object digest independently;
        # neither the repository name nor a moving branch identifies the bytes.
        return cls(
            resource_identity=(
                "huggingface:docling-project/docling-layout-heron-onnx"
            ),
            source_revision="40bde044036bb181c130ddf6c51792187268748f",
            artifact_name="model.onnx",
            artifact_sha256=SHA256Hash(
                "59c81a3a2923042d85034ffc487f8f47"
                "e4854117e879aef89b2b9f728fb4922a"
            ),
            artifact_byte_length=171_220_471,
            license_identity="Apache-2.0",
        )
