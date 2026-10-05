"""Fixed configurable pipeline execution pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import cast, final

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.pipeline.error import PipelineContractError
from projectkoios.ingestion.base.pipeline.identity import PipelineIdentity
from projectkoios.ingestion.base.pipeline.result import PipelineResult


class Pipeline[
    ConfigurationT: AbstractActionConfiguration,
    RequestT: ConfigurableDataObjectActionRequest,
    ResultT: PipelineResult,
](
    ConfigurableDataObjectActionizer[
        ConfigurationT,
        RequestT,
        ResultT,
    ],
    ABC,
):
    """Compose a fixed ordered set of action stages behind one typed action.

    Notes
    -----
    A pipeline owns synchronous domain composition only. It does not own queues,
    leases, retries, durable checkpoints, approval, scheduling, or cross-request
    workflow state. Those remain external Workflow responsibilities.
    """

    __slots__ = ()

    action_kind = "pipeline"
    has_external_effects: bool

    identity: PipelineIdentity
    request_type: type[RequestT]
    result_type: type[ResultT]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "action" in cls.__dict__:
            raise TypeError("pipelines cannot override the fixed action")
        if "__slots__" not in cls.__dict__:
            raise TypeError("pipelines must declare explicit instance slots")
        if cls.__dict__.get("action_kind", "pipeline") != "pipeline":
            raise TypeError("pipelines cannot change their action kind")

    @final
    def action(self, *, request: RequestT) -> ResultT:
        """Validate contracts and execute the fixed synchronous pipeline."""
        if type(request) is not self.request_type:
            raise PipelineContractError("pipeline request contract differs")
        if not isinstance(request, ConfigurableDataObjectActionRequest):
            raise PipelineContractError("pipeline request is not configurable")
        configurable = cast(
            ConfigurableDataObjectActionRequest[ConfigurationT],
            request,
        )
        try:
            configuration = self._require_configuration(request=configurable)
        except TypeError as error:
            raise PipelineContractError(
                "pipeline configuration contract differs"
            ) from error
        self._validate_identity()
        result = self.execute(
            request=request,
            configuration=configuration,
        )
        if type(result) is not self.result_type:
            raise PipelineContractError("pipeline result contract differs")
        return result

    @abstractmethod
    def execute(
        self,
        *,
        request: RequestT,
        configuration: ConfigurationT,
    ) -> ResultT:
        """Execute ordered synchronous stages for one complete request."""

    def _validate_identity(self) -> None:
        if not isinstance(self.identity, PipelineIdentity):
            raise PipelineContractError("pipeline identity is invalid")
        expected = (
            self.request_type.CONTRACT_NAME,
            self.configuration_type.CONTRACT_NAME,
            self.result_type.CONTRACT_NAME,
            self.has_external_effects,
        )
        actual = (
            self.identity.request_contract,
            self.identity.configuration_contract,
            self.identity.result_contract,
            self.identity.has_external_effects,
        )
        if actual != expected:
            raise PipelineContractError("pipeline identity contracts differ")
