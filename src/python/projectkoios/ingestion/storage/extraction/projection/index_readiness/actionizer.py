"""Provider actionizer for extraction projection index readiness."""

from __future__ import annotations

from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.backend import (  # noqa: E501
    ExtractionProjectionIndexReadinessBackend,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.backend_error import (  # noqa: E501
    ExtractionProjectionIndexReadinessBackendError,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.configuration import (  # noqa: E501
    ExtractionProjectionIndexReadinessConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.request import (  # noqa: E501
    ExtractionProjectionIndexReadinessRequest,
)
from projectkoios.ingestion.storage.extraction.projection.index_readiness.result import (  # noqa: E501
    ExtractionProjectionIndexReadinessResult,
)


class ExtractionProjectionIndexReadinessActionizer(
    ConfigurableDataObjectActionizer[
        ExtractionProjectionIndexReadinessConfiguration,
        ExtractionProjectionIndexReadinessRequest,
        ExtractionProjectionIndexReadinessResult,
    ]
):
    """Ensure required indexes and return exact observed evidence."""

    __slots__ = ("backend",)

    actionizer_name = "extraction-projection-index-readiness"
    actionizer_version = "1"
    configuration_type = ExtractionProjectionIndexReadinessConfiguration

    def __init__(
        self, *, backend: ExtractionProjectionIndexReadinessBackend
    ) -> None:
        if not isinstance(backend, ExtractionProjectionIndexReadinessBackend):
            raise TypeError("backend must be an index-readiness backend")
        self.backend = backend

    def action(
        self,
        *,
        request: ExtractionProjectionIndexReadinessRequest,
    ) -> ExtractionProjectionIndexReadinessResult:
        if type(request) is not ExtractionProjectionIndexReadinessRequest:
            raise TypeError("request must be an index-readiness request")
        configuration = self._require_configuration(request=request)
        try:
            evidence = self.backend.ensure_index_readiness(
                target=request.target,
                configuration=configuration,
                authority_id=request.authority_id,
            )
        except ExtractionProjectionIndexReadinessBackendError as error:
            return ExtractionProjectionIndexReadinessResult.failed(
                request=request,
                disposition=error.disposition,
                failure_code=error.code,
                actionizer_name=self.actionizer_name,
                actionizer_version=self.actionizer_version,
            )
        return ExtractionProjectionIndexReadinessResult.completed(
            request=request,
            evidence=evidence,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )
