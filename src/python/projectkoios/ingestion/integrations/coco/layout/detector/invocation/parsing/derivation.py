"""Single deterministic derivation for local detector output parsing."""

from projectkoios.ingestion.integrations.coco.layout.detector.actionizer import (  # noqa: E501
    CocoLayoutDetectorObservationActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.request import (
    CocoLayoutDetectorRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.result import (
    CocoLayoutDetectorResult,
)
from projectkoios.ingestion.json.error import JsonParseError

from ..output import (
    CocoLayoutDetectorRawOutput,
    CocoLayoutDetectorRawOutputJsonContract,
)
from ..result import CocoLayoutDetectorInvocationStatus
from .request import CocoLayoutDetectorOutputParsingRequest
from .status import CocoLayoutDetectorOutputParsingStatus


def derive_coco_layout_detector_output_parsing(
    request: CocoLayoutDetectorOutputParsingRequest,
) -> tuple[
    CocoLayoutDetectorOutputParsingStatus,
    CocoLayoutDetectorRawOutput | None,
    CocoLayoutDetectorResult | None,
    str | None,
]:
    """Derive the only parsing outcome from one exact invocation."""
    if type(request) is not CocoLayoutDetectorOutputParsingRequest:
        raise TypeError(
            "request must be CocoLayoutDetectorOutputParsingRequest"
        )
    invocation = request.invocation
    if invocation.status is not CocoLayoutDetectorInvocationStatus.COMPLETE:
        return (
            CocoLayoutDetectorOutputParsingStatus.INVOCATION_FAILED,
            None,
            None,
            "detector_invocation_failed",
        )
    content = invocation.raw_output_bytes
    if content is None:
        raise ValueError("complete invocation lost raw output bytes")
    try:
        raw_output = CocoLayoutDetectorRawOutputJsonContract().parse_bytes(
            content
        )
        invocation_request = invocation.request
        if (
            raw_output.render_id != invocation_request.render.render_id
            or raw_output.resource_id
            != invocation_request.configuration.resource.resource_id
            or raw_output.preprocessing_id
            != invocation_request.preprocessing.preprocessing_id
        ):
            raise ValueError(
                "raw detector output differs from invocation inputs"
            )
        detector_result = CocoLayoutDetectorObservationActionizer().action(
            request=CocoLayoutDetectorRequest(
                render=invocation_request.render,
                image=invocation_request.image,
                observations=raw_output.observations,
                configuration=invocation_request.configuration,
            )
        )
    except JsonParseError, TypeError, ValueError:
        return (
            CocoLayoutDetectorOutputParsingStatus.INVALID,
            None,
            None,
            "detector_output_invalid",
        )
    return (
        CocoLayoutDetectorOutputParsingStatus.VALID,
        raw_output,
        detector_result,
        None,
    )
