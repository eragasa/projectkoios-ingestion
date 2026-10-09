"""Immutable request for generic per-category COCO region admission."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.result import (  # noqa: E501
    CocoLayoutDetectorOutputParsingResult,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.status import (  # noqa: E501
    CocoLayoutDetectorOutputParsingStatus,
)
from projectkoios.ingestion.integrations.coco.layout.detector.result import (
    CocoLayoutDetectorResult,
)
from projectkoios.ingestion.integrations.coco.layout.result import (
    CocoLayoutProposalResult,
)

from .configuration import CocoLayoutRegionAdmissionConfiguration


@dataclass(frozen=True, slots=True)
class CocoLayoutRegionAdmissionRequest(
    ConfigurableDataObjectActionRequest[CocoLayoutRegionAdmissionConfiguration]
):
    """Bind exact parsed detector evidence to exact COCO proposals."""

    CONTRACT_NAME: ClassVar[str] = "coco-layout-region-admission-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    parsing_result: CocoLayoutDetectorOutputParsingResult
    proposal_result: CocoLayoutProposalResult
    configuration: CocoLayoutRegionAdmissionConfiguration
    request_id: str = field(init=False)

    @property
    def detector_result(self) -> CocoLayoutDetectorResult:
        """Return the exact detector result reconstructed from invocation."""
        detector_result = self.parsing_result.detector_result
        if detector_result is None:
            raise ValueError("valid parsing lost its detector result")
        return detector_result

    def __post_init__(self) -> None:
        if type(self.parsing_result) is not (
            CocoLayoutDetectorOutputParsingResult
        ):
            raise TypeError("parsing_result must be an output parsing result")
        if (
            self.parsing_result.status
            is not CocoLayoutDetectorOutputParsingStatus.VALID
            or type(self.parsing_result.detector_result)
            is not CocoLayoutDetectorResult
        ):
            raise ValueError("region admission requires valid parsing")
        if type(self.proposal_result) is not CocoLayoutProposalResult:
            raise TypeError("proposal_result must be CocoLayoutProposalResult")
        if type(self.configuration) is not (
            CocoLayoutRegionAdmissionConfiguration
        ):
            raise TypeError("configuration must be an admission configuration")
        detector_result = self.detector_result
        detector_request = detector_result.request
        proposal_request = self.proposal_result.request
        detector_configuration = detector_request.configuration
        proposal_configuration = proposal_request.configuration
        if (
            proposal_request.render != detector_request.render
            or proposal_request.image != detector_request.image
            or proposal_request.detections != detector_result.detections
        ):
            raise ValueError(
                "proposal result does not consume the exact detector result"
            )
        resource = detector_configuration.resource
        if (
            proposal_configuration.profile != detector_configuration.profile
            or proposal_configuration.detector_name
            != resource.resource_identity
            or proposal_configuration.detector_version
            != resource.source_revision
            or proposal_configuration.runtime_name
            != detector_configuration.runtime_name
            or proposal_configuration.runtime_version
            != detector_configuration.runtime_version
            or proposal_configuration.resource_identity
            != resource.resource_identity
            or proposal_configuration.resource_sha256
            != resource.artifact_sha256
            or proposal_configuration.max_detections
            != detector_configuration.maximum_observations
        ):
            raise ValueError(
                "proposal configuration differs from detector evidence"
            )
        if self.configuration.profile != detector_configuration.profile:
            raise ValueError("admission profile differs from detector evidence")
        if (
            self.configuration.minimum_confidence
            < detector_configuration.minimum_confidence
        ):
            raise ValueError(
                "admission confidence cannot weaken detector filtering"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                self.CONTRACT_NAME,
                self.CONTRACT_VERSION,
                self.parsing_result.result_id,
                self.proposal_result.result_id,
                self.configuration.configuration_id,
            ),
        )
