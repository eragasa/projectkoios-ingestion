"""Strict local detector raw-output parser and normalizer."""

from projectkoios.base import DataObjectActionizer

from .derivation import derive_coco_layout_detector_output_parsing
from .request import CocoLayoutDetectorOutputParsingRequest
from .result import CocoLayoutDetectorOutputParsingResult


class CocoLayoutDetectorOutputParser(
    DataObjectActionizer[
        CocoLayoutDetectorOutputParsingRequest,
        CocoLayoutDetectorOutputParsingResult,
    ]
):
    """Parse canonical provider output before deterministic normalization."""

    __slots__ = ()

    def action(
        self, *, request: CocoLayoutDetectorOutputParsingRequest
    ) -> CocoLayoutDetectorOutputParsingResult:
        """Return exact valid evidence or one explicit parsing failure."""
        status, raw_output, detector_result, failure_code = (
            derive_coco_layout_detector_output_parsing(request)
        )
        return CocoLayoutDetectorOutputParsingResult(
            request=request,
            status=status,
            raw_output=raw_output,
            detector_result=detector_result,
            failure_code=failure_code,
        )
