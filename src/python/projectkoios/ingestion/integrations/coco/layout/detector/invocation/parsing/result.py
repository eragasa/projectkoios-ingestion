"""Strict local detector raw-output parsing results."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detector.result import (
    CocoLayoutDetectorResult,
)

from ..output import CocoLayoutDetectorRawOutput
from .derivation import derive_coco_layout_detector_output_parsing
from .request import CocoLayoutDetectorOutputParsingRequest
from .status import CocoLayoutDetectorOutputParsingStatus


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorOutputParsingResult(AbstractDataObjectActionResult):
    """Retain strict parsing status and exact valid normalized evidence."""

    request: CocoLayoutDetectorOutputParsingRequest
    status: CocoLayoutDetectorOutputParsingStatus
    raw_output: CocoLayoutDetectorRawOutput | None
    detector_result: CocoLayoutDetectorResult | None
    failure_code: str | None
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutDetectorOutputParsingRequest:
            raise TypeError(
                "request must be CocoLayoutDetectorOutputParsingRequest"
            )
        if not isinstance(self.status, CocoLayoutDetectorOutputParsingStatus):
            raise TypeError(
                "status must be CocoLayoutDetectorOutputParsingStatus"
            )
        if self.status is CocoLayoutDetectorOutputParsingStatus.VALID:
            if type(self.raw_output) is not CocoLayoutDetectorRawOutput:
                raise ValueError("valid parsing requires typed raw output")
            if type(self.detector_result) is not CocoLayoutDetectorResult:
                raise ValueError("valid parsing requires detector result")
            if self.failure_code is not None:
                raise ValueError("valid parsing cannot carry failure code")
            invocation_request = self.request.invocation.request
            if (
                self.raw_output.render_id != invocation_request.render.render_id
                or self.raw_output.resource_id
                != invocation_request.configuration.resource.resource_id
                or self.raw_output.preprocessing_id
                != invocation_request.preprocessing.preprocessing_id
            ):
                raise ValueError("parsed output differs from invocation inputs")
            detector_request = self.detector_result.request
            if (
                detector_request.render != invocation_request.render
                or detector_request.image != invocation_request.image
                or detector_request.configuration
                != invocation_request.configuration
                or detector_request.observations != self.raw_output.observations
            ):
                raise ValueError(
                    "detector result differs from parsed invocation output"
                )
        else:
            if self.raw_output is not None or self.detector_result is not None:
                raise ValueError(
                    "failed parsing cannot carry normalized output"
                )
            if not self.failure_code:
                raise ValueError("failed parsing requires failure code")
        expected = derive_coco_layout_detector_output_parsing(self.request)
        if (
            self.status,
            self.raw_output,
            self.detector_result,
            self.failure_code,
        ) != expected:
            raise ValueError("parsing result differs from exact derivation")
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "coco-layout-detector-output-parsing-result",
                self.request.request_id,
                self.status,
                self.raw_output.output_id if self.raw_output else None,
                (
                    self.detector_result.result_id
                    if self.detector_result
                    else None
                ),
                self.failure_code,
            ),
        )
