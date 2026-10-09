"""Reusable framework-neutral local detector adapter fixtures."""

from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.integrations.coco.layout.actionizer import (
    CocoLayoutRegionProposalActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.configuration import (
    CocoLayoutProposalConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detector.configuration import (  # noqa: E501
    CocoLayoutDetectorConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.configuration import (  # noqa: E501
    CocoLayoutDetectorGateConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.request import (  # noqa: E501
    CocoLayoutDetectorGateRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.output import (  # noqa: E501
    CocoLayoutDetectorRawOutput,
    CocoLayoutDetectorRawOutputJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.actionizer import (  # noqa: E501
    CocoLayoutDetectorOutputParser,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.request import (  # noqa: E501
    CocoLayoutDetectorOutputParsingRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.result import (  # noqa: E501
    CocoLayoutDetectorOutputParsingResult,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.preprocessing import (  # noqa: E501
    CocoLayoutDetectorPreprocessing,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.request import (  # noqa: E501
    CocoLayoutDetectorInvocationRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.result import (  # noqa: E501
    CocoLayoutDetectorInvocationResult,
    CocoLayoutDetectorInvocationStatus,
)
from projectkoios.ingestion.integrations.coco.layout.detector.label import (
    CocoLayoutDetectorLabelMappingInventory,
)
from projectkoios.ingestion.integrations.coco.layout.detector.observation import (  # noqa: E501
    CocoLayoutDetectorObservation,
    CocoLayoutDetectorObservationInventory,
)
from projectkoios.ingestion.integrations.coco.layout.detector.request import (
    CocoLayoutDetectorRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.resource import (
    CocoLayoutDetectorResource,
)
from projectkoios.ingestion.integrations.coco.layout.image import (
    CocoLayoutImage,
)
from projectkoios.ingestion.integrations.coco.layout.profile import (
    CocoLayoutProfile,
)
from projectkoios.ingestion.integrations.coco.layout.request import (
    CocoLayoutProposalRequest,
)
from projectkoios.ingestion.layout.contracts import DeterministicLayoutProcessor
from projectkoios.ingestion.layout.review.actionizer import (
    DeterministicLayoutReviewActionizer,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)


def coco_layout_detector_configuration() -> CocoLayoutDetectorConfiguration:
    """Return a synthetic configuration without claiming model execution."""
    return CocoLayoutDetectorConfiguration(
        profile=CocoLayoutProfile.koios_doclaynet_v0_1(),
        resource=CocoLayoutDetectorResource(
            resource_identity="fixture:heron-compatible-detector",
            source_revision="fixture-revision-1",
            artifact_name="fixture-model.onnx",
            artifact_sha256=SHA256Hash("c" * 64),
            artifact_byte_length=1,
            license_identity="fixture-only",
        ),
        runtime_name="fixture-runtime",
        runtime_version="1.0",
        label_mappings=(
            CocoLayoutDetectorLabelMappingInventory.docling_heron_v0_1()
        ),
        minimum_confidence=0.5,
        maximum_observations=300,
    )


def coco_layout_invocation_request() -> CocoLayoutDetectorInvocationRequest:
    """Build one exact synthetic invocation request."""
    detector_request = coco_layout_detector_request()
    render = detector_request.render
    return CocoLayoutDetectorInvocationRequest(
        render=render,
        image=detector_request.image,
        image_reference=ManagedArtifactReference(
            sha256=render.image_sha256,
            byte_length=123,
            media_type=ManagedArtifactMediaType(render.image_media_type),
        ),
        configuration=detector_request.configuration,
        preprocessing=(
            CocoLayoutDetectorPreprocessing.docling_heron_onnx_v0_1()
        ),
        provider_implementation_id="fixture-detector-provider:1.0",
        execution_provider="fixture-execution-provider",
        execution_device_identity="fixture-device",
        maximum_output_bytes=10_000,
    )


def coco_layout_detector_raw_output() -> CocoLayoutDetectorRawOutput:
    """Build canonical synthetic provider output for one invocation."""
    invocation_request = coco_layout_invocation_request()
    return CocoLayoutDetectorRawOutput(
        render_id=invocation_request.render.render_id,
        resource_id=invocation_request.configuration.resource.resource_id,
        preprocessing_id=invocation_request.preprocessing.preprocessing_id,
        observations=coco_layout_detector_request().observations,
    )


def coco_layout_detector_completed_invocation() -> (
    CocoLayoutDetectorInvocationResult
):
    """Build one complete invocation with canonical synthetic output."""
    request = coco_layout_invocation_request()
    output = CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(
        coco_layout_detector_raw_output()
    )
    return CocoLayoutDetectorInvocationResult(
        request=request,
        status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        request_document_bytes=request.document_bytes(),
        raw_output_bytes=output,
        elapsed_nanoseconds=1,
        failure_kind=None,
        failure_code=None,
    )


def coco_layout_detector_request(
    *,
    reverse: bool = False,
    include_limitations: bool = True,
    omit_formula: bool = False,
    duplicate_formula: bool = False,
) -> CocoLayoutDetectorRequest:
    """Return accepted, unsupported, and below-threshold observations."""
    _, _, render = LayoutReviewFixture().render_evidence()
    image = CocoLayoutImage(
        image_id=1,
        render_id=render.render_id,
        width=render.image_width,
        height=render.image_height,
        image_media_type=render.image_media_type,
        image_sha256=render.image_sha256,
    )
    observations: tuple[CocoLayoutDetectorObservation, ...] = (
        CocoLayoutDetectorObservation(
            render_id=render.render_id,
            model_label_id=9,
            bounding_box_xyxy_pixels=(20.0, 80.0, 80.0, 100.0),
            confidence=0.95,
        ),
        CocoLayoutDetectorObservation(
            render_id=render.render_id,
            model_label_id=12,
            bounding_box_xyxy_pixels=(90.0, 20.0, 120.0, 40.0),
            confidence=0.99,
        ),
        CocoLayoutDetectorObservation(
            render_id=render.render_id,
            model_label_id=0,
            bounding_box_xyxy_pixels=(20.0, 50.0, 80.0, 65.0),
            confidence=0.1,
        ),
        CocoLayoutDetectorObservation(
            render_id=render.render_id,
            model_label_id=2,
            bounding_box_xyxy_pixels=(20.0, 20.0, 80.0, 40.0),
            confidence=0.9,
        ),
    )
    if not include_limitations:
        observations = (observations[0], observations[3])
    if duplicate_formula:
        observations += (
            CocoLayoutDetectorObservation(
                render_id=render.render_id,
                model_label_id=2,
                bounding_box_xyxy_pixels=(21.0, 21.0, 79.0, 39.0),
                confidence=0.85,
            ),
        )
    if omit_formula:
        observations = tuple(
            observation
            for observation in observations
            if observation.model_label_id != 2
        )
    if reverse:
        observations = tuple(reversed(observations))
    return CocoLayoutDetectorRequest(
        render=render,
        image=image,
        observations=CocoLayoutDetectorObservationInventory(*observations),
        configuration=coco_layout_detector_configuration(),
    )


def coco_layout_detector_parsing_result(
    detector_request: CocoLayoutDetectorRequest,
) -> CocoLayoutDetectorOutputParsingResult:
    """Bind synthetic observations to exact completed invocation evidence."""
    invocation_request = coco_layout_invocation_request()
    raw_output = CocoLayoutDetectorRawOutput(
        render_id=invocation_request.render.render_id,
        resource_id=invocation_request.configuration.resource.resource_id,
        preprocessing_id=invocation_request.preprocessing.preprocessing_id,
        observations=detector_request.observations,
    )
    invocation = CocoLayoutDetectorInvocationResult(
        request=invocation_request,
        status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        request_document_bytes=invocation_request.document_bytes(),
        raw_output_bytes=(
            CocoLayoutDetectorRawOutputJsonContract().serialize_bytes(
                raw_output
            )
        ),
        elapsed_nanoseconds=1,
        failure_kind=None,
        failure_code=None,
    )
    return CocoLayoutDetectorOutputParser().action(
        request=CocoLayoutDetectorOutputParsingRequest(invocation=invocation)
    )


def coco_layout_gate_request(
    *,
    include_limitations: bool = False,
    omit_formula: bool = False,
    duplicate_formula: bool = False,
    gate_configuration: CocoLayoutDetectorGateConfiguration | None = None,
) -> CocoLayoutDetectorGateRequest:
    """Build an exact detector-to-proposal-to-review evidence chain."""
    detector_request = coco_layout_detector_request(
        include_limitations=include_limitations,
        omit_formula=omit_formula,
        duplicate_formula=duplicate_formula,
    )
    parsing_result = coco_layout_detector_parsing_result(detector_request)
    detector_result = parsing_result.detector_result
    if detector_result is None:
        raise ValueError("fixture detector parsing unexpectedly failed")
    detector_configuration = detector_request.configuration
    resource = detector_configuration.resource
    proposal_result = CocoLayoutRegionProposalActionizer().action(
        request=CocoLayoutProposalRequest(
            render=detector_request.render,
            image=detector_request.image,
            detections=detector_result.detections,
            configuration=CocoLayoutProposalConfiguration(
                profile=detector_configuration.profile,
                detector_name=resource.resource_identity,
                detector_version=resource.source_revision,
                runtime_name=detector_configuration.runtime_name,
                runtime_version=detector_configuration.runtime_version,
                resource_identity=resource.resource_identity,
                resource_sha256=resource.artifact_sha256,
                max_detections=detector_configuration.maximum_observations,
            ),
        )
    )
    source, page = LayoutReviewFixture().source_page()
    layout = DeterministicLayoutProcessor().analyze_page(source, page)
    review_case = DeterministicLayoutReviewActionizer().action(
        request=LayoutReviewRequest.create(
            layout=layout,
            render=detector_request.render,
            proposal_source=proposal_result.proposal_source,
            proposals=proposal_result.proposals,
        )
    )
    return CocoLayoutDetectorGateRequest(
        parsing_result=parsing_result,
        proposal_result=proposal_result,
        review_case=review_case,
        configuration=(
            gate_configuration or CocoLayoutDetectorGateConfiguration()
        ),
    )
