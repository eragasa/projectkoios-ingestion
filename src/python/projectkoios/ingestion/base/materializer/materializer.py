"""Fixed effectful materializer execution pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import final

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.materializer.configuration import (
    AbstractMaterializationConfiguration,
)
from projectkoios.ingestion.base.materializer.error import (
    MaterializationContractError,
)
from projectkoios.ingestion.base.materializer.evidence import (
    AbstractMaterializationEvidence,
)
from projectkoios.ingestion.base.materializer.identity import (
    MaterializerIdentity,
)
from projectkoios.ingestion.base.materializer.identity_error import (
    MaterializationIdentityError,
)
from projectkoios.ingestion.base.materializer.request import (
    MaterializationRequest,
)
from projectkoios.ingestion.base.materializer.result import (
    MaterializationResult,
)
from projectkoios.ingestion.base.materializer.target import (
    AbstractMaterializationTarget,
)
from projectkoios.ingestion.base.projector.value import AbstractProjectionValue


class Materializer[
    ProjectionT: AbstractProjectionValue,
    TargetT: AbstractMaterializationTarget,
    ConfigurationT: AbstractMaterializationConfiguration,
    EvidenceT: AbstractMaterializationEvidence,
](
    ConfigurableDataObjectActionizer[
        ConfigurationT,
        MaterializationRequest[ProjectionT, TargetT, ConfigurationT],
        MaterializationResult[EvidenceT],
    ],
    ABC,
):
    """Apply one immutable projection to one explicit external target.

    Notes
    -----
    A materializer is effectful. It consumes a complete projection, explicit
    target identity, complete physical write configuration, and authority
    identity. It returns immutable outcome evidence. It does not project source
    evidence, select work, query inventories, authorize policy, retry, or own
    workflow state.

    Concrete implementations may hold explicit adapter capabilities such as a
    database handle, but must declare their instance slots. ``action`` remains
    fixed so every materializer performs the same contract checks.
    """

    __slots__ = ()

    action_kind = "materialization"
    has_external_effects = True

    identity: MaterializerIdentity
    authority_requirement: str
    projection_type: type[ProjectionT]
    target_type: type[TargetT]
    configuration_type: type[ConfigurationT]
    evidence_type: type[EvidenceT]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "action" in cls.__dict__:
            raise TypeError("materializers cannot override the fixed action")
        if "__slots__" not in cls.__dict__:
            raise TypeError(
                "materializers must declare explicit instance slots"
            )
        if cls.__dict__.get("action_kind", "materialization") != (
            "materialization"
        ):
            raise TypeError("materializers cannot change their action kind")
        if cls.__dict__.get("has_external_effects", True) is not True:
            raise TypeError("materializers must declare external effects")

    @final
    def action(
        self,
        *,
        request: MaterializationRequest[
            ProjectionT,
            TargetT,
            ConfigurationT,
        ],
    ) -> MaterializationResult[EvidenceT]:
        """Validate, apply, and bind one materialization result.

        Raises
        ------
        TypeError
            If the fixed request or a declared value type differs.
        MaterializationContractError
            If implementation contracts or produced evidence differ.
        MaterializationIdentityError
            If schema, authority, target, or provenance identities differ.
        """
        if not isinstance(request, MaterializationRequest):
            raise TypeError("request must be a MaterializationRequest")
        if type(request.projection) is not self.projection_type:
            raise MaterializationContractError(
                "materializer projection contract differs"
            )
        if type(request.target) is not self.target_type:
            raise MaterializationContractError(
                "materializer target contract differs"
            )
        try:
            configuration = self._require_configuration(request=request)
        except TypeError as error:
            raise MaterializationContractError(
                "materializer configuration contract differs"
            ) from error
        self._validate_identity(request=request)
        evidence = self.materialize(
            projection=request.projection,
            target=request.target,
            configuration=configuration,
            authority_id=request.authority_id,
        )
        if type(evidence) is not self.evidence_type:
            raise MaterializationContractError(
                "materializer evidence contract differs"
            )
        if (
            evidence.projection_id != request.projection.projection_id
            or evidence.target_id != request.target.target_id
            or evidence.configuration_id
            != request.configuration.configuration_id
            or evidence.authority_id != request.authority_id
        ):
            raise MaterializationIdentityError(
                "materialization evidence provenance differs"
            )
        return MaterializationResult.create(
            request=request,
            materializer=self.identity,
            evidence=evidence,
        )

    @abstractmethod
    def materialize(
        self,
        *,
        projection: ProjectionT,
        target: TargetT,
        configuration: ConfigurationT,
        authority_id: str,
    ) -> EvidenceT:
        """Perform target effects and return immutable outcome evidence."""

    def _validate_identity(
        self,
        *,
        request: MaterializationRequest[
            ProjectionT,
            TargetT,
            ConfigurationT,
        ],
    ) -> None:
        if not isinstance(self.identity, MaterializerIdentity):
            raise MaterializationIdentityError(
                "materializer identity is invalid"
            )
        expected = (
            self.projection_type.CONTRACT_NAME,
            self.target_type.CONTRACT_NAME,
            self.configuration_type.CONTRACT_NAME,
            self.evidence_type.CONTRACT_NAME,
            self.authority_requirement,
        )
        actual = (
            self.identity.projection_contract,
            self.identity.target_contract,
            self.identity.configuration_contract,
            self.identity.evidence_contract,
            self.identity.authority_requirement,
        )
        if actual != expected:
            raise MaterializationIdentityError(
                "materializer identity contracts differ"
            )
        if not (
            request.projection.schema_id
            == request.target.schema_id
            == request.configuration.schema_id
            == self.identity.schema_id
        ):
            raise MaterializationIdentityError(
                "materialization schema identities differ"
            )
