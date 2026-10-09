"""Fail-closed orchestration tests for the private layout-equation canary."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, replace

import pytest
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.recognition.processor.identity import (
    EquationRecognitionProcessorIdentity,
)
from projectkoios.ingestion.equations.recognition.proposal import (
    EquationRecognitionProposal,
)
from projectkoios.ingestion.equations.recognition.resource import (
    EquationRecognitionResource,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.admission.actionizer import (  # noqa: E501
    CocoLayoutRegionAdmissionActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.admission.configuration import (  # noqa: E501
    CocoLayoutRegionAdmissionConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.admission.outcome import (  # noqa: E501
    CocoLayoutCategoryAdmissionStatus,
)
from projectkoios.ingestion.integrations.coco.layout.admission.request import (  # noqa: E501
    CocoLayoutRegionAdmissionRequest,
)
from projectkoios.ingestion.integrations.coco.layout.admission.result import (
    CocoLayoutRegionAdmissionResult,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.parsing.status import (  # noqa: E501
    CocoLayoutDetectorOutputParsingStatus,
)
from projectkoios.ingestion.integrations.coco.layout.detector.invocation.result import (  # noqa: E501
    CocoLayoutDetectorInvocationStatus,
)
from projectkoios.ingestion.integrations.coco.layout.equation.actionizer import (  # noqa: E501
    CocoLayoutEquationProjectionActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.equation.assembler import (
    CocoLayoutEquationAssembler,
)
from projectkoios.ingestion.integrations.coco.layout.equation.configuration import (  # noqa: E501
    CocoLayoutEquationProjectionConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.equation.request import (
    CocoLayoutEquationProjectionRequest,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter

from scripts.layout_equation_canary import (
    LayoutEquationCanaryBridgeStatus,
    LayoutEquationCanaryPageResult,
    LayoutEquationCanaryStageStatus,
    LayoutEquationCanaryTrustedEvidence,
    execute_layout_equation_canary_downstream,
    summarize_layout_equation_canary_pages,
    verify_layout_equation_canary_document,
)
from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_gate_request,
)
from tests.projectkoios.ingestion.integrations.coco.layout.equation.test__CocoLayoutEquationProjection import (  # noqa: E501
    FixtureEquationRenderer,
    equation_projection_request,
)


def region_admission(
    *,
    omit_formula: bool = False,
    minimum_confidence: float = 0.5,
) -> CocoLayoutRegionAdmissionResult:
    """Build exact generic admission evidence for the canary fixture."""
    source = coco_layout_gate_request(
        include_limitations=True,
        omit_formula=omit_formula,
    )
    detector_result = source.parsing_result.detector_result
    if detector_result is None:
        raise ValueError("fixture parsing unexpectedly failed")
    return CocoLayoutRegionAdmissionActionizer().action(
        request=CocoLayoutRegionAdmissionRequest(
            parsing_result=source.parsing_result,
            proposal_result=source.proposal_result,
            configuration=CocoLayoutRegionAdmissionConfiguration(
                profile=detector_result.request.configuration.profile,
                minimum_confidence=minimum_confidence,
            ),
        )
    )


def admitted_formula_page() -> LayoutEquationCanaryPageResult:
    """Return one internally consistent completed positive-path page."""
    return LayoutEquationCanaryPageResult(
        case_id="case-admitted-formula",
        source_sha256="a" * 64,
        page_index=2,
        invocation_status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        parsing_status=CocoLayoutDetectorOutputParsingStatus.VALID,
        formula_admission_status=(CocoLayoutCategoryAdmissionStatus.ADMITTED),
        accepted_formula_detection_count=2,
        projection_status=LayoutEquationCanaryStageStatus.COMPLETE,
        projection_candidate_count=2,
        projection_exclusion_count=0,
        assembly_status=LayoutEquationCanaryStageStatus.COMPLETE,
        assembly_count=2,
        recognition_status=LayoutEquationCanaryStageStatus.COMPLETE,
        recognition_proposal_count=2,
        recognition_proposed_count=2,
        recognition_failed_count=0,
        recognition_not_requested_count=0,
        failure_code=None,
    )


def fixture_recognition_artifact(
    assembly_artifact_id: str, assembly_id: str
) -> EquationRecognitionArtifact:
    """Return one exact completed recognition artifact with no proposal text."""
    processor = EquationRecognitionProcessorIdentity(
        processor_name="fixture-recognizer",
        processor_version="1",
        backend_name="fixture-backend",
        backend_version="1",
        executable_sha256="e" * 64,
        executable_semantic_sha256="f" * 64,
        resources=(
            EquationRecognitionResource(
                name="fixture",
                path="fixture://resource",
                sha256="d" * 64,
                byte_size=1,
            ),
        ),
        temperature=0.01,
    )
    proposal = EquationRecognitionProposal(
        proposal_id=stable_id(
            "equation-recognition-proposal",
            EQUATION_RECOGNITION_CONTRACT_VERSION,
            assembly_id,
            EquationRecognitionStatus.NOT_REQUESTED,
            None,
            None,
            (),
            None,
            processor.identity_digest,
        ),
        assembly_id=assembly_id,
        status=EquationRecognitionStatus.NOT_REQUESTED,
        latex=None,
        mathml=None,
        mathml_processor_identity=None,
        mathml_processor_version=None,
        warning_codes=(),
        failure_message=None,
        processor_identity_digest=processor.identity_digest,
    )
    diagnostic_sha256 = SHA256Fingerprinter.fingerprint(content=b"")
    artifact_id = stable_id(
        "equation-recognition-artifact",
        EQUATION_RECOGNITION_CONTRACT_VERSION,
        assembly_artifact_id,
        processor.identity_digest,
        (proposal.proposal_id,),
        0,
        0,
        diagnostic_sha256,
    )
    return EquationRecognitionArtifact(
        artifact_id=artifact_id,
        assembly_artifact_id=assembly_artifact_id,
        processor_identity=processor,
        proposals=(proposal,),
        invocation_exit_code=0,
        diagnostic_byte_size=0,
        diagnostic_sha256=diagnostic_sha256,
    )


def escalated_formula_page() -> LayoutEquationCanaryPageResult:
    """Return one formula-bearing page stopped by the admission gate."""
    return LayoutEquationCanaryPageResult(
        case_id="case-escalated-formula",
        source_sha256="b" * 64,
        page_index=4,
        invocation_status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        parsing_status=CocoLayoutDetectorOutputParsingStatus.VALID,
        formula_admission_status=(
            CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED
        ),
        accepted_formula_detection_count=3,
        projection_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        projection_candidate_count=None,
        projection_exclusion_count=None,
        assembly_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        assembly_count=None,
        recognition_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        recognition_proposal_count=None,
        recognition_proposed_count=None,
        recognition_failed_count=None,
        recognition_not_requested_count=None,
        failure_code="formula_admission_escalation_required",
    )


def test_empty_formula_admission_never_calls_downstream_actions() -> None:
    admission = region_admission(omit_formula=True)

    def forbidden(*_args: object) -> object:
        raise AssertionError("downstream action was called")

    evidence = execute_layout_equation_canary_downstream(
        admission_result=admission,
        project=forbidden,  # type: ignore[arg-type]
        assemble=forbidden,  # type: ignore[arg-type]
        recognize=forbidden,  # type: ignore[arg-type]
    )

    assert evidence.projection is None
    assert evidence.assembly is None
    assert evidence.recognition is None


def test_admission_cannot_authorize_projection_from_another_result() -> None:
    request = equation_projection_request()
    supplied_admission = request.admission_result
    other_admission = region_admission(minimum_confidence=0.8)
    assert supplied_admission != other_admission
    other_projection = CocoLayoutEquationProjectionActionizer().action(
        request=CocoLayoutEquationProjectionRequest(
            document=request.document,
            admission_result=other_admission,
            configuration=CocoLayoutEquationProjectionConfiguration(),
        )
    )

    def forbidden(*_args: object) -> object:
        raise AssertionError("later downstream action was called")

    with pytest.raises(ValueError, match="differs from supplied admission"):
        execute_layout_equation_canary_downstream(
            admission_result=supplied_admission,
            project=lambda: other_projection,
            assemble=forbidden,  # type: ignore[arg-type]
            recognize=forbidden,  # type: ignore[arg-type]
        )


def test_admission_escalation_cannot_report_projection_or_assembly() -> None:
    page = escalated_formula_page()

    with pytest.raises(
        ValueError, match="formula admission escalation stops projection"
    ):
        replace(
            page,
            projection_status=LayoutEquationCanaryStageStatus.COMPLETE,
            projection_candidate_count=3,
            projection_exclusion_count=0,
        )


def test_failed_invocation_requires_every_later_stage_not_evaluated() -> None:
    page = LayoutEquationCanaryPageResult(
        case_id="case-invocation-failed",
        source_sha256="d" * 64,
        page_index=1,
        invocation_status=CocoLayoutDetectorInvocationStatus.FAILED,
        parsing_status=None,
        formula_admission_status=None,
        accepted_formula_detection_count=None,
        projection_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        projection_candidate_count=None,
        projection_exclusion_count=None,
        assembly_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        assembly_count=None,
        recognition_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        recognition_proposal_count=None,
        recognition_proposed_count=None,
        recognition_failed_count=None,
        recognition_not_requested_count=None,
        failure_code="detector_invocation_failed",
    )

    with pytest.raises(ValueError, match="stops parsing"):
        replace(
            page,
            parsing_status=CocoLayoutDetectorOutputParsingStatus.INVALID,
        )


def test_invalid_parsing_requires_every_downstream_stage_not_evaluated() -> (
    None
):
    page = LayoutEquationCanaryPageResult(
        case_id="case-invalid-parsing",
        source_sha256="c" * 64,
        page_index=0,
        invocation_status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        parsing_status=CocoLayoutDetectorOutputParsingStatus.INVALID,
        formula_admission_status=None,
        accepted_formula_detection_count=None,
        projection_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        projection_candidate_count=None,
        projection_exclusion_count=None,
        assembly_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        assembly_count=None,
        recognition_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        recognition_proposal_count=None,
        recognition_proposed_count=None,
        recognition_failed_count=None,
        recognition_not_requested_count=None,
        failure_code="detector_output_invalid",
    )

    assert page.parsing_status is CocoLayoutDetectorOutputParsingStatus.INVALID
    with pytest.raises(
        ValueError, match="invalid parsing stops admission evaluation"
    ):
        replace(
            page,
            formula_admission_status=(
                CocoLayoutCategoryAdmissionStatus.ADMITTED
            ),
        )


def test_admitted_formula_page_requires_exact_stage_counts() -> None:
    page = admitted_formula_page()

    assert page.assembly_count == page.projection_candidate_count
    assert page.recognition_proposal_count == page.assembly_count
    with pytest.raises(ValueError, match="assembly count must equal"):
        replace(page, assembly_count=1)


def test_projection_counts_must_cover_every_accepted_formula() -> None:
    with pytest.raises(
        ValueError,
        match="projection candidates and exclusions must cover every",
    ):
        replace(
            admitted_formula_page(),
            accepted_formula_detection_count=1,
            recognition_proposed_count=1,
            recognition_not_requested_count=1,
        )


def test_admitted_formula_category_requires_positive_count() -> None:
    with pytest.raises(ValueError, match="requires a positive formula count"):
        replace(
            admitted_formula_page(),
            accepted_formula_detection_count=0,
            projection_candidate_count=0,
            assembly_count=0,
            recognition_proposal_count=0,
            recognition_proposed_count=0,
            recognition_failed_count=0,
            recognition_not_requested_count=0,
        )


def test_escalated_formula_category_requires_positive_count() -> None:
    with pytest.raises(ValueError, match="requires a positive formula count"):
        replace(
            escalated_formula_page(),
            accepted_formula_detection_count=0,
        )


def test_empty_formula_category_is_evaluated_as_zero() -> None:
    page = replace(
        admitted_formula_page(),
        case_id="case-admitted-without-formula",
        formula_admission_status=CocoLayoutCategoryAdmissionStatus.EMPTY,
        accepted_formula_detection_count=0,
        projection_candidate_count=0,
        assembly_count=0,
        recognition_proposal_count=0,
        recognition_proposed_count=0,
        recognition_failed_count=0,
        recognition_not_requested_count=0,
    )

    assert page.projection_status is LayoutEquationCanaryStageStatus.COMPLETE
    assert page.assembly_status is LayoutEquationCanaryStageStatus.COMPLETE
    assert page.recognition_status is LayoutEquationCanaryStageStatus.COMPLETE


def test_admitted_downstream_failure_is_reported_as_failed() -> None:
    page = replace(
        admitted_formula_page(),
        recognition_status=LayoutEquationCanaryStageStatus.FAILED,
        recognition_proposal_count=None,
        recognition_proposed_count=None,
        recognition_failed_count=None,
        recognition_not_requested_count=None,
        failure_code="recognition_failed",
    )

    summary = summarize_layout_equation_canary_pages((page,))

    assert summary.bridge_status is LayoutEquationCanaryBridgeStatus.FAILED
    assert summary.failed_bridge_page_count == 1


def test_summary_never_reports_escalated_pages_as_evaluated() -> None:
    summary = summarize_layout_equation_canary_pages(
        (escalated_formula_page(),)
    )

    assert (
        summary.bridge_status is LayoutEquationCanaryBridgeStatus.NOT_EVALUATED
    )
    assert summary.formula_bearing_page_count == 1
    assert summary.bridge_evaluated_formula_page_count == 0
    assert summary.formula_escalation_page_count == 1


def canary_document(
    pages: tuple[LayoutEquationCanaryPageResult, ...],
) -> dict[str, object]:
    """Return one JSON-shaped result document for verifier tests."""
    summary = summarize_layout_equation_canary_pages(pages)
    page_values = json.loads(json.dumps([asdict(page) for page in pages]))
    summary_value = json.loads(json.dumps(asdict(summary)))
    records = []
    for page in pages:
        record = {
            "case_id": page.case_id,
            "source_sha256": page.source_sha256,
            "page_index": page.page_index,
            "invocation_status": page.invocation_status.value,
            "parsing_status": (
                None
                if page.parsing_status is None
                else page.parsing_status.value
            ),
            "formula_admission_status": (
                None
                if page.formula_admission_status is None
                else page.formula_admission_status.value
            ),
            "formula_detection_count": (page.accepted_formula_detection_count),
        }
        if page.formula_admission_status is not None:
            record["admission_result_id"] = "admission:fixture"
        if page.projection_status is LayoutEquationCanaryStageStatus.COMPLETE:
            record["projection_result_id"] = "projection:fixture"
        if page.assembly_status is LayoutEquationCanaryStageStatus.COMPLETE:
            record["assembly_artifact_id"] = "assembly:fixture"
        if page.recognition_status is LayoutEquationCanaryStageStatus.COMPLETE:
            record["recognition_artifact_id"] = "recognition:fixture"
        records.append(record)
    return {
        "schema_version": "private-layout-equation-canary-v4",
        "authority": "non-authoritative private capability evidence",
        "model_resource_id": "resource:fixture",
        "preprocessing_id": "preprocessing:fixture",
        "preprocessing_original_size_order": "width_height",
        "recognition_processor_identity": "recognizer:fixture",
        "page_results": page_values,
        "summary": summary_value,
        "evidence_records": records,
    }


def bind_document_to_trusted_evidence(
    document: dict[str, object],
    trusted: LayoutEquationCanaryTrustedEvidence,
) -> None:
    """Bind top-level fixture identities to independent typed evidence."""
    parsing_result = trusted.admission_result.request.parsing_result
    invocation_request = parsing_result.request.invocation.request
    document["model_resource_id"] = (
        invocation_request.configuration.resource.resource_id
    )
    document["preprocessing_id"] = (
        invocation_request.preprocessing.preprocessing_id
    )
    document["preprocessing_original_size_order"] = (
        invocation_request.preprocessing.original_size_order.value
    )
    if trusted.recognition is not None:
        document["recognition_processor_identity"] = (
            trusted.recognition.processor_identity.identity_digest
        )


def test_canary_document_verifier_rejects_false_evaluation_claim() -> None:
    document = canary_document((escalated_formula_page(),))

    summary = verify_layout_equation_canary_document(document)

    assert (
        summary.bridge_status is LayoutEquationCanaryBridgeStatus.NOT_EVALUATED
    )
    forged = copy.deepcopy(document)
    assert isinstance(forged["summary"], dict)
    forged["summary"]["bridge_status"] = "evaluated"
    with pytest.raises(ValueError, match="summary differs"):
        verify_layout_equation_canary_document(forged)


def test_verifier_rejects_self_consistent_forged_admission() -> None:
    document = canary_document((admitted_formula_page(),))

    with pytest.raises(ValueError, match="independently trusted evidence"):
        verify_layout_equation_canary_document(document)


def test_canary_document_verifier_rejects_downstream_identity_after_stop() -> (
    None
):
    document = canary_document((escalated_formula_page(),))
    records = document["evidence_records"]
    assert isinstance(records, list)
    assert isinstance(records[0], dict)
    records[0]["projection_result_id"] = "projection:forged"

    with pytest.raises(ValueError, match="stopped stage contains"):
        verify_layout_equation_canary_document(document)


def test_canary_document_verifier_binds_stage_identities_independently() -> (
    None
):
    request = equation_projection_request()
    projection = CocoLayoutEquationProjectionActionizer().action(
        request=request
    )
    source_sha256 = request.document.source.content_hash
    detector_request = request.admission_result.request.detector_result.request
    page_index = detector_request.render.page_index
    projection_page = LayoutEquationCanaryPageResult(
        case_id="case-assembly-failed",
        source_sha256=source_sha256,
        page_index=page_index,
        invocation_status=CocoLayoutDetectorInvocationStatus.COMPLETE,
        parsing_status=CocoLayoutDetectorOutputParsingStatus.VALID,
        formula_admission_status=(CocoLayoutCategoryAdmissionStatus.ADMITTED),
        accepted_formula_detection_count=1,
        projection_status=LayoutEquationCanaryStageStatus.COMPLETE,
        projection_candidate_count=len(projection.candidates),
        projection_exclusion_count=len(projection.exclusions),
        assembly_status=LayoutEquationCanaryStageStatus.FAILED,
        assembly_count=None,
        recognition_status=LayoutEquationCanaryStageStatus.NOT_EVALUATED,
        recognition_proposal_count=None,
        recognition_proposed_count=None,
        recognition_failed_count=None,
        recognition_not_requested_count=None,
        failure_code="assembly_failed",
    )
    trusted_projection = LayoutEquationCanaryTrustedEvidence(
        case_id=projection_page.case_id,
        source_sha256=source_sha256,
        page_index=page_index,
        admission_result=request.admission_result,
        projection=projection,
        assembly=None,
        recognition=None,
    )
    document = canary_document((projection_page,))
    bind_document_to_trusted_evidence(document, trusted_projection)
    record = document["evidence_records"][0]  # type: ignore[index]
    assert isinstance(record, dict)
    record["admission_result_id"] = request.admission_result.result_id
    record["projection_result_id"] = projection.result_id

    verify_layout_equation_canary_document(
        document, trusted_evidence=(trusted_projection,)
    )
    for field in (
        "model_resource_id",
        "preprocessing_id",
        "preprocessing_original_size_order",
    ):
        forged = copy.deepcopy(document)
        forged[field] = "forged"
        with pytest.raises(ValueError, match=field):
            verify_layout_equation_canary_document(
                forged, trusted_evidence=(trusted_projection,)
            )
    record["assembly_artifact_id"] = "assembly:forged"
    with pytest.raises(ValueError, match="stopped stage contains"):
        verify_layout_equation_canary_document(
            document, trusted_evidence=(trusted_projection,)
        )

    assembly = CocoLayoutEquationAssembler(
        renderer=FixtureEquationRenderer()
    ).assemble(projection, b"layout review fixture")
    recognition_page = replace(
        projection_page,
        case_id="case-recognition-failed",
        assembly_status=LayoutEquationCanaryStageStatus.COMPLETE,
        assembly_count=len(assembly.assemblies),
        recognition_status=LayoutEquationCanaryStageStatus.FAILED,
        failure_code="recognition_failed",
    )
    trusted_assembly = LayoutEquationCanaryTrustedEvidence(
        case_id=recognition_page.case_id,
        source_sha256=source_sha256,
        page_index=page_index,
        admission_result=request.admission_result,
        projection=projection,
        assembly=assembly,
        recognition=None,
    )
    document = canary_document((recognition_page,))
    bind_document_to_trusted_evidence(document, trusted_assembly)
    record = document["evidence_records"][0]  # type: ignore[index]
    assert isinstance(record, dict)
    record["admission_result_id"] = request.admission_result.result_id
    record["projection_result_id"] = projection.result_id
    record["assembly_artifact_id"] = assembly.artifact_id

    verify_layout_equation_canary_document(
        document, trusted_evidence=(trusted_assembly,)
    )
    record["recognition_artifact_id"] = "recognition:forged"
    with pytest.raises(ValueError, match="stopped stage contains"):
        verify_layout_equation_canary_document(
            document, trusted_evidence=(trusted_assembly,)
        )

    recognition = fixture_recognition_artifact(
        assembly.artifact_id,
        assembly.assemblies[0].assembly_id,
    )
    completed_page = replace(
        recognition_page,
        case_id="case-recognition-complete",
        recognition_status=LayoutEquationCanaryStageStatus.COMPLETE,
        recognition_proposal_count=len(recognition.proposals),
        recognition_proposed_count=0,
        recognition_failed_count=0,
        recognition_not_requested_count=len(recognition.proposals),
        failure_code=None,
    )
    trusted_recognition = LayoutEquationCanaryTrustedEvidence(
        case_id=completed_page.case_id,
        source_sha256=source_sha256,
        page_index=page_index,
        admission_result=request.admission_result,
        projection=projection,
        assembly=assembly,
        recognition=recognition,
    )
    document = canary_document((completed_page,))
    bind_document_to_trusted_evidence(document, trusted_recognition)
    record = document["evidence_records"][0]  # type: ignore[index]
    assert isinstance(record, dict)
    record["admission_result_id"] = request.admission_result.result_id
    record["projection_result_id"] = projection.result_id
    record["assembly_artifact_id"] = assembly.artifact_id
    record["recognition_artifact_id"] = recognition.artifact_id

    verified = verify_layout_equation_canary_document(
        document, trusted_evidence=(trusted_recognition,)
    )
    assert verified.bridge_status is (
        LayoutEquationCanaryBridgeStatus.NOT_EVALUATED
    )
    assert verified.recognition_not_requested_formula_count == 1
    assert verified.recognition_proposed_formula_count == 0
    document["recognition_processor_identity"] = "recognizer:forged"
    with pytest.raises(ValueError, match="recognition_processor_identity"):
        verify_layout_equation_canary_document(
            document, trusted_evidence=(trusted_recognition,)
        )


def test_failed_recognition_proposal_fails_bridge_summary() -> None:
    page = replace(
        admitted_formula_page(),
        recognition_proposed_count=1,
        recognition_failed_count=1,
    )

    summary = summarize_layout_equation_canary_pages((page,))

    assert summary.bridge_status is LayoutEquationCanaryBridgeStatus.FAILED
    assert summary.failed_bridge_page_count == 1
    assert summary.recognition_failed_formula_count == 1


def test_summary_distinguishes_partial_from_complete_evaluation() -> None:
    partial = summarize_layout_equation_canary_pages(
        (admitted_formula_page(), escalated_formula_page())
    )
    complete = summarize_layout_equation_canary_pages(
        (admitted_formula_page(),)
    )

    assert partial.bridge_status is (
        LayoutEquationCanaryBridgeStatus.PARTIALLY_EVALUATED
    )
    assert complete.bridge_status is LayoutEquationCanaryBridgeStatus.EVALUATED
