"""Immutable requests for deterministic local-detector admission."""

from __future__ import annotations

from dataclasses import dataclass, field

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
from projectkoios.ingestion.layout.review.result import LayoutReviewCase

from .configuration import CocoLayoutDetectorGateConfiguration


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorGateRequest(
    ConfigurableDataObjectActionRequest[CocoLayoutDetectorGateConfiguration]
):
    """Bind detector, proposal, and deterministic review evidence exactly."""

    parsing_result: CocoLayoutDetectorOutputParsingResult
    proposal_result: CocoLayoutProposalResult
    review_case: LayoutReviewCase
    configuration: CocoLayoutDetectorGateConfiguration
    request_id: str = field(init=False)

    @property
    def detector_result(self) -> CocoLayoutDetectorResult:
        """Return the exact detector result reconstructed from invocation."""
        detector_result = self.parsing_result.detector_result
        if detector_result is None:
            raise ValueError("valid parsing lost its detector result")
        return detector_result

    def __post_init__(self) -> None:
        if (
            type(self.parsing_result)
            is not CocoLayoutDetectorOutputParsingResult
        ):
            raise TypeError(
                "parsing_result must be CocoLayoutDetectorOutputParsingResult"
            )
        if (
            self.parsing_result.status
            is not CocoLayoutDetectorOutputParsingStatus.VALID
            or type(self.parsing_result.detector_result)
            is not CocoLayoutDetectorResult
        ):
            raise ValueError("gate requires valid detector invocation parsing")
        if type(self.proposal_result) is not CocoLayoutProposalResult:
            raise TypeError("proposal_result must be CocoLayoutProposalResult")
        if type(self.review_case) is not LayoutReviewCase:
            raise TypeError("review_case must be LayoutReviewCase")
        if type(self.configuration) is not CocoLayoutDetectorGateConfiguration:
            raise TypeError(
                "configuration must be CocoLayoutDetectorGateConfiguration"
            )
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
        if (
            self.review_case.request.render != detector_request.render
            or self.review_case.request.proposal_source
            != self.proposal_result.proposal_source
            or self.review_case.request.proposals
            != self.proposal_result.proposals
        ):
            raise ValueError(
                "layout review does not consume the exact proposal result"
            )
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "coco-layout-detector-gate-request",
                self.parsing_result.result_id,
                self.proposal_result.result_id,
                self.review_case.case_id,
                self.configuration.configuration_id,
            ),
        )
