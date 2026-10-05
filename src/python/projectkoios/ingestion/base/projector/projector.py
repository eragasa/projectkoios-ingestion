"""Fixed pure projector execution pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import final

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.projector.configuration import (
    AbstractProjectionConfiguration,
)
from projectkoios.ingestion.base.projector.error import (
    ProjectionContractError,
)
from projectkoios.ingestion.base.projector.identity import ProjectorIdentity
from projectkoios.ingestion.base.projector.identity_error import (
    ProjectionIdentityError,
)
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
    ConfigurableDataObjectActionizer[
        ConfigurationT,
        ProjectionRequest[SourceT, ConfigurationT],
        ProjectionResult[ProjectionT],
    ],
    ABC,
):
    """Map complete immutable evidence to a rebuildable projection.

    Notes
    -----
    Concrete projectors supply only :meth:`project`. The framework fixes action
    validation and result construction, and prohibits instance state, authority
    requirements, and external effects. A projector therefore cannot read a
    database, consult mutable process state, or materialize its output.
    """

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
        """Execute the fixed pure projection action.

        Parameters
        ----------
        request
            Canonical source evidence and complete deterministic
            configuration.

        Returns
        -------
        ProjectionResult[ProjectionT]
            The projection bound to its request and projector identities.

        Raises
        ------
        TypeError
            If ``request`` is not the fixed projection request type.
        ProjectionContractError
            If source, configuration, or output contracts differ from the
            projector declaration.
        ProjectionIdentityError
            If the projector identity does not bind those declarations.
        """
        if not isinstance(request, ProjectionRequest):
            raise TypeError("request must be a ProjectionRequest")
        if any(
            type(source) is not self.source_type for source in request.sources
        ):
            raise ProjectionContractError("projector source contract differs")
        try:
            configuration = self._require_configuration(request=request)
        except TypeError as error:
            raise ProjectionContractError(
                "projector configuration contract differs"
            ) from error
        self._validate_identity()
        projection = self.project(
            sources=request.sources,
            configuration=configuration,
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
        """Derive one projection using only supplied immutable values.

        Parameters
        ----------
        sources
            Canonically ordered, unique, immutable source evidence.
        configuration
            Complete immutable configuration for the transformation.

        Returns
        -------
        ProjectionT
            One immutable, rebuildable projection value.
        """

    def _validate_identity(self) -> None:
        # Identity validation is distinct from input-shape validation: all
        # classes may be structurally valid while naming a different contract.
        if not isinstance(self.identity, ProjectorIdentity):
            raise ProjectionIdentityError("projector identity is invalid")
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
            raise ProjectionIdentityError("projector identity contracts differ")
