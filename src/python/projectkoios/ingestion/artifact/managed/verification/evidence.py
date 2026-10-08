"""Immutable exact managed-artifact verification observations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.artifact.managed.limits.error import (
    ManagedArtifactLimitError,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class ManagedArtifactVerificationEvidence(AbstractImmutableDataObject):
    """Record one successful bounded byte and media-signature observation."""

    reference: ManagedArtifactReference
    observed_sha256: SHA256Hash
    observed_byte_length: int
    observed_media_type: ManagedArtifactMediaType
    provider_implementation_id: str
    verifier_implementation_id: str
    evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.reference) is not ManagedArtifactReference:
            raise TypeError(
                "reference must be an exact managed artifact reference"
            )
        digest = MANAGED_ARTIFACT_LIMITS.require_sha256(
            self.observed_sha256, "observed_sha256"
        )
        length = MANAGED_ARTIFACT_LIMITS.require_byte_length(
            self.observed_byte_length, "observed_byte_length"
        )
        if not isinstance(self.observed_media_type, ManagedArtifactMediaType):
            raise TypeError("observed_media_type is unsupported")
        provider_id = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            self.provider_implementation_id, "provider_implementation_id"
        )
        verifier_id = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            self.verifier_implementation_id, "verifier_implementation_id"
        )
        if (
            digest != self.reference.sha256
            or length != self.reference.byte_length
            or self.observed_media_type is not self.reference.media_type
        ):
            raise ValueError(
                "observed artifact evidence differs from its reference"
            )
        object.__setattr__(self, "observed_sha256", digest)
        object.__setattr__(self, "provider_implementation_id", provider_id)
        object.__setattr__(self, "verifier_implementation_id", verifier_id)
        object.__setattr__(
            self,
            "evidence_id",
            stable_id(
                "managed-artifact-verification-evidence",
                self.reference.artifact_id,
                digest,
                length,
                self.observed_media_type,
                provider_id,
                verifier_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class ManagedArtifactVerificationEvidenceInventory:
    """Own exact one-to-one successful coverage for one reference inventory."""

    reference_inventory_id: str
    _evidence: tuple[ManagedArtifactVerificationEvidence, ...] = field(
        repr=True
    )
    aggregate_observed_byte_length: int
    inventory_id: str = field(init=False)

    def __init__(
        self,
        references: ManagedArtifactReferenceInventory,
        *evidence: ManagedArtifactVerificationEvidence,
    ) -> None:
        if type(references) is not ManagedArtifactReferenceInventory:
            raise TypeError("references must be a managed artifact inventory")
        values = tuple(evidence)
        if len(values) > MANAGED_ARTIFACT_LIMITS.maximum_verifications:
            raise ManagedArtifactLimitError(
                "managed artifact verification count exceeds its limit"
            )
        if any(
            type(value) is not ManagedArtifactVerificationEvidence
            for value in values
        ):
            raise TypeError("verification inventory requires exact evidence")
        evidence_artifact_ids = tuple(
            value.reference.artifact_id for value in values
        )
        expected_artifact_ids = tuple(
            reference.artifact_id for reference in references
        )
        if evidence_artifact_ids != tuple(sorted(evidence_artifact_ids)):
            raise ValueError("managed artifact evidence must be sorted")
        if len(evidence_artifact_ids) != len(set(evidence_artifact_ids)):
            raise ValueError("managed artifact evidence must be unique")
        if evidence_artifact_ids != expected_artifact_ids:
            raise ValueError(
                "managed artifact evidence does not exactly cover references"
            )
        for reference, observation in zip(references, values, strict=True):
            if observation.reference != reference:
                raise ValueError(
                    "managed artifact evidence contains a stale reference"
                )
        aggregate = sum(value.observed_byte_length for value in values)
        if aggregate > MANAGED_ARTIFACT_LIMITS.maximum_aggregate_bytes:
            raise ManagedArtifactLimitError(
                "managed artifact observed bytes exceed their limit"
            )
        object.__setattr__(
            self, "reference_inventory_id", references.inventory_id
        )
        object.__setattr__(self, "_evidence", values)
        object.__setattr__(self, "aggregate_observed_byte_length", aggregate)
        member_identity_digest = SHA256Fingerprinter.fingerprint_chunks(
            chunks=(
                CanonicalJsonSerializer.serialize_bytes(value.evidence_id)
                for value in values
            )
        )
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "managed-artifact-verification-evidence-inventory",
                references.inventory_id,
                len(values),
                aggregate,
                member_identity_digest,
            ),
        )

    def __iter__(self) -> Iterator[ManagedArtifactVerificationEvidence]:
        return iter(self._evidence)

    def __len__(self) -> int:
        return len(self._evidence)

    def require(self, artifact_id: str) -> ManagedArtifactVerificationEvidence:
        """Return exact evidence for one referenced artifact or fail closed."""
        for evidence in self._evidence:
            if evidence.reference.artifact_id == artifact_id:
                return evidence
        raise ValueError("managed artifact verification evidence is absent")
