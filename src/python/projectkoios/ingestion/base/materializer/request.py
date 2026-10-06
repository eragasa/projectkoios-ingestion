"""Fixed request envelope for every ingestion materializer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.materializer.configuration import (
    AbstractMaterializationConfiguration,
)
from projectkoios.ingestion.base.materializer.identity.error import (
    MaterializationIdentityError,
)
from projectkoios.ingestion.base.materializer.target import (
    AbstractMaterializationTarget,
)
from projectkoios.ingestion.base.projector.value import AbstractProjectionValue
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class MaterializationRequest[
    ProjectionT: AbstractProjectionValue,
    TargetT: AbstractMaterializationTarget,
    ConfigurationT: AbstractMaterializationConfiguration,
](
    AbstractImmutableDataObject,
    ConfigurableDataObjectActionRequest[ConfigurationT],
):
    """Bind one projection, target, configuration, and authority identity.

    Parameters
    ----------
    request_id
        Stable request identity that includes the invoking authority identity.
    idempotency_key
        Stable operation identity independent of the invoking authority.
    projection
        Complete immutable projection value to apply.
    target
        Explicit globally unambiguous external target identity.
    configuration
        Complete immutable physical write configuration.
    authority_id
        Identity of the granted authority used for this request.
    contract_version
        Version of this fixed request envelope.
    """

    CONTRACT_NAME: ClassVar[str] = "materialization-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_TEXT_LENGTH: ClassVar[int] = 4_096

    request_id: str
    idempotency_key: str
    projection: ProjectionT
    target: TargetT
    configuration: ConfigurationT
    authority_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection: ProjectionT,
        target: TargetT,
        configuration: ConfigurationT,
        authority_id: str,
    ) -> MaterializationRequest[ProjectionT, TargetT, ConfigurationT]:
        """Create the fixed request envelope.

        Returns
        -------
        MaterializationRequest[ProjectionT, TargetT, ConfigurationT]
            Request binding exact content, target, configuration, and authority.
        """
        if not isinstance(projection, AbstractProjectionValue):
            raise TypeError("materialization projection is invalid")
        if not isinstance(target, AbstractMaterializationTarget):
            raise TypeError("materialization target is invalid")
        if not isinstance(configuration, AbstractMaterializationConfiguration):
            raise TypeError("materialization configuration is invalid")
        idempotency_key = cls._idempotency(
            projection=projection,
            target=target,
            configuration=configuration,
        )
        return cls(
            request_id=stable_id(
                "materialization-request",
                cls.CONTRACT_VERSION,
                authority_id,
                idempotency_key,
            ),
            idempotency_key=idempotency_key,
            projection=projection,
            target=target,
            configuration=configuration,
            authority_id=authority_id,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported materialization-request contract")
        if not isinstance(self.projection, AbstractProjectionValue):
            raise TypeError("materialization projection is invalid")
        if not isinstance(self.target, AbstractMaterializationTarget):
            raise TypeError("materialization target is invalid")
        if not isinstance(
            self.configuration, AbstractMaterializationConfiguration
        ):
            raise TypeError("materialization configuration is invalid")
        for name, value in (
            ("projection_id", self.projection.projection_id),
            ("target_id", self.target.target_id),
            ("configuration_id", self.configuration.configuration_id),
            ("schema_id", self.projection.schema_id),
            ("authority_id", self.authority_id),
        ):
            if (
                type(value) is not str
                or not value
                or len(value) > self.MAXIMUM_TEXT_LENGTH
            ):
                raise ValueError(f"materialization {name} is invalid")
        if not SHA256Hash.is_canonical(self.projection.canonical_sha256):
            raise ValueError("materialization projection digest is invalid")
        if not (
            self.projection.schema_id
            == self.target.schema_id
            == self.configuration.schema_id
        ):
            raise MaterializationIdentityError(
                "materialization schema identities differ"
            )
        expected_idempotency = self._idempotency(
            projection=self.projection,
            target=self.target,
            configuration=self.configuration,
        )
        if self.idempotency_key != expected_idempotency:
            raise ValueError("materialization idempotency is inconsistent")
        expected_request = stable_id(
            "materialization-request",
            self.CONTRACT_VERSION,
            self.authority_id,
            self.idempotency_key,
        )
        if self.request_id != expected_request:
            raise ValueError("materialization request ID is inconsistent")

    @classmethod
    def _idempotency(
        cls,
        *,
        projection: AbstractProjectionValue,
        target: AbstractMaterializationTarget,
        configuration: AbstractMaterializationConfiguration,
    ) -> str:
        return stable_id(
            "materialization-idempotency",
            cls.CONTRACT_VERSION,
            projection.projection_id,
            projection.canonical_sha256,
            target.target_id,
            configuration.configuration_id,
        )
