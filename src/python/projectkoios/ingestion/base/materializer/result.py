"""Fixed result envelope for every ingestion materializer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.materializer.configuration import (
    AbstractMaterializationConfiguration,
)
from projectkoios.ingestion.base.materializer.evidence import (
    AbstractMaterializationEvidence,
)
from projectkoios.ingestion.base.materializer.identity import (
    MaterializerIdentity,
)
from projectkoios.ingestion.base.materializer.request import (
    MaterializationRequest,
)
from projectkoios.ingestion.base.materializer.target import (
    AbstractMaterializationTarget,
)
from projectkoios.ingestion.base.projector.value import AbstractProjectionValue
from projectkoios.ingestion.identity import stable_id

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class MaterializationResult[EvidenceT: AbstractMaterializationEvidence](
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Bind materialization evidence to request and implementation identities.

    Parameters
    ----------
    result_id
        Stable identity over request, materializer, and evidence identities.
    request_id
        Identity of the exact materialization request.
    idempotency_key
        Stable operation identity copied from the request.
    materializer
        Exact effectful implementation identity.
    evidence
        Immutable observed outcome evidence.
    contract_version
        Version of this fixed result envelope.
    """

    CONTRACT_NAME: ClassVar[str] = "materialization-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    idempotency_key: str
    materializer: MaterializerIdentity
    evidence: EvidenceT
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create[
        ProjectionT: AbstractProjectionValue,
        TargetT: AbstractMaterializationTarget,
        ConfigurationT: AbstractMaterializationConfiguration,
    ](
        cls,
        *,
        request: MaterializationRequest[
            ProjectionT,
            TargetT,
            ConfigurationT,
        ],
        materializer: MaterializerIdentity,
        evidence: EvidenceT,
    ) -> MaterializationResult[EvidenceT]:
        """Create the fixed result envelope from exact outcome evidence."""
        return cls(
            result_id=stable_id(
                "materialization-result",
                cls.CONTRACT_VERSION,
                request.request_id,
                request.idempotency_key,
                materializer.materializer_id,
                evidence.evidence_id,
                evidence.canonical_sha256,
            ),
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            materializer=materializer,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported materialization-result contract")
        for name, value in (
            ("request_id", self.request_id),
            ("idempotency_key", self.idempotency_key),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"materialization result {name} is invalid")
        if not isinstance(self.materializer, MaterializerIdentity):
            raise TypeError("materialization result identity is invalid")
        if not isinstance(self.evidence, AbstractMaterializationEvidence):
            raise TypeError("materialization result evidence is invalid")
        if (
            type(self.evidence.evidence_id) is not str
            or not self.evidence.evidence_id
            or type(self.evidence.canonical_sha256) is not str
            or not _SHA256.fullmatch(self.evidence.canonical_sha256)
        ):
            raise ValueError("materialization evidence identity is invalid")
        expected = stable_id(
            "materialization-result",
            self.CONTRACT_VERSION,
            self.request_id,
            self.idempotency_key,
            self.materializer.materializer_id,
            self.evidence.evidence_id,
            self.evidence.canonical_sha256,
        )
        if self.result_id != expected:
            raise ValueError("materialization result ID is inconsistent")
