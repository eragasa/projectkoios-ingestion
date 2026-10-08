"""Immutable successful managed-artifact verification results."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.artifact.managed.verification.evidence import (
    ManagedArtifactVerificationEvidenceInventory,
)
from projectkoios.ingestion.artifact.managed.verification.request import (
    ManagedArtifactVerificationRequest,
)
from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class ManagedArtifactVerificationResult(AbstractDataObjectActionResult):
    """Bind one exact request to complete successful verification evidence."""

    request: ManagedArtifactVerificationRequest
    evidence: ManagedArtifactVerificationEvidenceInventory
    verifier_implementation_id: str
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not ManagedArtifactVerificationRequest:
            raise TypeError(
                "request must be a managed artifact verification request"
            )
        if (
            type(self.evidence)
            is not ManagedArtifactVerificationEvidenceInventory
        ):
            raise TypeError(
                "evidence must be a verification evidence inventory"
            )
        verifier_id = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            self.verifier_implementation_id, "verifier_implementation_id"
        )
        if (
            self.evidence.reference_inventory_id
            != self.request.references.inventory_id
        ):
            raise ValueError(
                "verification evidence covers different references"
            )
        if (
            self.evidence.aggregate_observed_byte_length
            != self.request.references.aggregate_byte_length
            or self.evidence.aggregate_observed_byte_length
            > self.request.maximum_aggregate_bytes
        ):
            raise ValueError(
                "verification evidence has an invalid aggregate byte count"
            )
        if any(
            item.provider_implementation_id
            != self.request.provider_implementation_id
            or item.verifier_implementation_id != verifier_id
            for item in self.evidence
        ):
            raise ValueError(
                "verification evidence has an incompatible implementation"
            )
        object.__setattr__(self, "verifier_implementation_id", verifier_id)
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "managed-artifact-verification-result",
                self.request.request_id,
                self.evidence.inventory_id,
                verifier_id,
            ),
        )
