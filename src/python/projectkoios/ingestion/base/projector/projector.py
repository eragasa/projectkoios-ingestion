"""Fixed pure projector execution pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import final

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.base.projector.configuration import (
    AbstractProjectionConfiguration,
)
from projectkoios.ingestion.base.projector.error import (
    ProjectionContractError,
)
from projectkoios.ingestion.base.projector.identity import ProjectorIdentity
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.base.projector.result import ProjectionResult
from projectkoios.ingestion.base.projector.source import (
    AbstractProjectionSource,
)
from projectkoios.ingestion.base.projector.value import AbstractProjectionValue


class Projector[
    SourceT: AbstractProjectionSource,
    ConfigurationT: AbstractProjectionConfiguration,
    ProjectionT: AbstractProjectionValue,
](
    DataObjectActionizer[
        ProjectionRequest[SourceT, ConfigurationT],
        ProjectionResult[ProjectionT],
    ],
    ABC,
):
    """Pure mapping from complete evidence to a rebuildable view."""

    __slots__ = ()

    action_kind = "projection"
    has_external_effects = False
    authority_requirements: tuple[str, ...] = ()

    identity: ProjectorIdentity
    source_type: type[SourceT]
    configuration_type: type[ConfigurationT]
    projection_type: type[ProjectionT]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "action" in cls.__dict__:
            raise TypeError(
                "projectors cannot override the fixed action method"
            )
        if "__init__" in cls.__dict__:
            raise TypeError("projectors cannot define instance initialization")
        if cls.__dict__.get("__slots__") != ():
            raise TypeError("projectors must be stateless")
        if cls.__dict__.get("action_kind", "projection") != "projection":
            raise TypeError("projectors cannot change their action kind")
        if cls.__dict__.get("has_external_effects", False) is not False:
            raise TypeError("projectors cannot declare external effects")
        if cls.__dict__.get("authority_requirements", ()) != ():
            raise TypeError("projectors cannot require authority")

    @final
    def action(
        self,
        *,
        request: ProjectionRequest[SourceT, ConfigurationT],
    ) -> ProjectionResult[ProjectionT]:
        if not isinstance(request, ProjectionRequest):
            raise TypeError("request must be a ProjectionRequest")
        if any(
            type(source) is not self.source_type for source in request.sources
        ):
            raise ProjectionContractError("projector source contract differs")
        if type(request.configuration) is not self.configuration_type:
            raise ProjectionContractError(
                "projector configuration contract differs"
            )
        self._validate_identity()
        projection = self.project(
            sources=request.sources,
            configuration=request.configuration,
        )
        if type(projection) is not self.projection_type:
            raise ProjectionContractError("projector output contract differs")
        return ProjectionResult.create(
            request=request,
            projector=self.identity,
            projection=projection,
        )

    @abstractmethod
    def project(
        self,
        *,
        sources: tuple[SourceT, ...],
        configuration: ConfigurationT,
    ) -> ProjectionT:
        """Derive one projection using only the supplied immutable values."""

    def _validate_identity(self) -> None:
        if not isinstance(self.identity, ProjectorIdentity):
            raise ProjectionContractError("projector identity is invalid")
        expected = (
            self.source_type.CONTRACT_NAME,
            self.configuration_type.CONTRACT_NAME,
            self.projection_type.CONTRACT_NAME,
        )
        actual = (
            self.identity.source_contract,
            self.identity.configuration_contract,
            self.identity.projection_contract,
        )
        if actual != expected:
            raise ProjectionContractError("projector identity contracts differ")
