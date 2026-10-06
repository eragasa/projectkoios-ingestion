"""Fixed result envelope for every ingestion projector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.projector.configuration import (
    AbstractProjectionConfiguration,
)
from projectkoios.ingestion.base.projector.identity.model import (
    ProjectorIdentity,
)
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.base.projector.source import (
    AbstractProjectionSource,
)
from projectkoios.ingestion.base.projector.value import AbstractProjectionValue
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class ProjectionResult[ProjectionT: AbstractProjectionValue](
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    """Bind one projection value to request and projector identities.

    Parameters
    ----------
    result_id
        Stable identity over request, projector, sources, and output content.
    request_id
        Identity of the exact projection request.
    source_evidence_ids
        Canonically ordered source identities copied from the request.
    projector
        Exact implementation and schema identity.
    projection
        Immutable rebuildable output value.
    contract_version
        Version of this fixed result envelope.
    """

    CONTRACT_NAME: ClassVar[str] = "projection-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result_id: str
    request_id: str
    source_evidence_ids: tuple[str, ...]
    projector: ProjectorIdentity
    projection: ProjectionT
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create[
        SourceT: AbstractProjectionSource,
        ConfigurationT: AbstractProjectionConfiguration,
    ](
        cls,
        *,
        request: ProjectionRequest[SourceT, ConfigurationT],
        projector: ProjectorIdentity,
        projection: ProjectionT,
    ) -> ProjectionResult[ProjectionT]:
        """Create the fixed result envelope.

        Parameters
        ----------
        request
            Exact validated request that produced the output.
        projector
            Exact projector implementation identity.
        projection
            Immutable rebuildable output value.

        Returns
        -------
        ProjectionResult[ProjectionT]
            Result binding all provenance and content identities.

        Raises
        ------
        TypeError
            If projector or projection values have incompatible contracts.
        ValueError
            If source, schema, digest, or result identities differ.
        """
        source_ids = tuple(source.evidence_id for source in request.sources)
        return cls(
            result_id=stable_id(
                "projection-result",
                cls.CONTRACT_VERSION,
                request.request_id,
                source_ids,
                projector.projector_id,
                projection.projection_id,
                projection.canonical_sha256,
            ),
            request_id=request.request_id,
            source_evidence_ids=source_ids,
            projector=projector,
            projection=projection,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported projection-result contract")
        if type(self.request_id) is not str or not self.request_id:
            raise ValueError("projection result request identity is invalid")
        if (
            not isinstance(self.source_evidence_ids, tuple)
            or not self.source_evidence_ids
            or any(
                type(evidence_id) is not str or not evidence_id
                for evidence_id in self.source_evidence_ids
            )
            or self.source_evidence_ids
            != tuple(sorted(set(self.source_evidence_ids)))
        ):
            raise ValueError("projection result source identities are invalid")
        if not isinstance(self.projector, ProjectorIdentity):
            raise TypeError("projection result projector identity is invalid")
        if not isinstance(self.projection, AbstractProjectionValue):
            raise TypeError("projection result value is invalid")
        if (
            type(self.projection.projection_id) is not str
            or not self.projection.projection_id
            or type(self.projection.schema_id) is not str
            or not self.projection.schema_id
            or not SHA256Hash.is_canonical(self.projection.canonical_sha256)
        ):
            raise ValueError("projection value identity is invalid")
        if self.projection.source_evidence_ids != self.source_evidence_ids:
            raise ValueError("projection result source identities differ")
        if self.projection.schema_id != self.projector.schema_id:
            raise ValueError("projection result schema identity differs")
        expected = stable_id(
            "projection-result",
            self.CONTRACT_VERSION,
            self.request_id,
            self.source_evidence_ids,
            self.projector.projector_id,
            self.projection.projection_id,
            self.projection.canonical_sha256,
        )
        if self.result_id != expected:
            raise ValueError("projection result ID is inconsistent")
