from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path

import pytest
from projectkoios.ingestion import (
    DeterministicFigureCandidateDetector,
    FigureRelevanceProcessor,
    PyMuPdfExtractor,
    SourceDocument,
    WarningSeverity,
)
from projectkoios.ingestion.figure_relevance import (
    FigureRelevanceConfidence,
    FigureRelevanceConfiguration,
    FigureRelevanceFailure,
    FigureRelevanceFailureKind,
    FigureRelevanceLevel,
    FigureRelevanceLimitError,
    FigureRelevanceProcessorIdentity,
    FigureRelevanceProposal,
    FigureRelevanceRequest,
    FigureRelevanceResourceIdentity,
    FigureRelevanceResourceIdentityKind,
    FigureRelevanceResult,
    FigureRelevanceScore,
    FigureRelevanceSelection,
    FigureRelevanceSelectionResult,
    FigureRelevanceStatus,
    FigureRelevanceWarning,
    build_figure_relevance_cache_key,
)

pytest.importorskip("pymupdf")


def _detection(fixture_name: str, suffix: str):
    fixture = Path(__file__).parent / "fixtures" / "pdf" / f"{fixture_name}.pdf"
    payload = fixture.read_bytes()
    source = SourceDocument.from_bytes(
        payload,
        source_id=f"article:figure-relevance:{suffix}",
        media_type="application/pdf",
        locator=f"memory://figure-relevance-{suffix}.pdf",
    )
    document = PyMuPdfExtractor().extract(source, BytesIO(payload)).document
    return DeterministicFigureCandidateDetector().detect(
        document, BytesIO(payload)
    )


def _selection(fixture_name: str = "figures", suffix: str = "selection"):
    detection = _detection(fixture_name, suffix)
    return FigureRelevanceSelection.create(
        detection_result=detection,
        candidate_id=detection.candidates[0].candidate_id,
    )


def _identity(model: str = "model-v1") -> FigureRelevanceProcessorIdentity:
    return FigureRelevanceProcessorIdentity(
        processor_name="static-figure-relevance",
        processor_version="1",
        backend_name="fixture-backend",
        backend_version="1",
        resources=(
            FigureRelevanceResourceIdentity(
                resource_name="model",
                identity_kind=FigureRelevanceResourceIdentityKind.EXPLICIT,
                resource_identity=model,
            ),
        ),
    )


def _score(value: float) -> FigureRelevanceScore:
    return FigureRelevanceScore(
        value=value,
        method="fixture-relevance-score",
        method_version="1",
        scale="0_irrelevant_to_1_necessary",
    )


def _confidence() -> FigureRelevanceConfidence:
    return FigureRelevanceConfidence(
        value=0.82,
        method="fixture-confidence",
        method_version="1",
        scale="0_unassessed_to_1_high",
    )


def _request(
    selection: FigureRelevanceSelection,
    *,
    question: str = "Is this figure necessary to explain the measured trend?",
    configuration: FigureRelevanceConfiguration | None = None,
) -> FigureRelevanceRequest:
    return FigureRelevanceRequest.create(
        review_question=question,
        selections=(selection,),
        configuration=configuration,
    )


def _proposal(
    request: FigureRelevanceRequest,
    *,
    value: float = 0.91,
    rationale: str = (
        "The plotted evidence directly addresses the review question."
    ),
) -> FigureRelevanceProposal:
    selection = request.selections[0]
    candidate = selection.candidate
    return FigureRelevanceProposal.create(
        selection=selection,
        configuration=request.configuration,
        score=_score(value),
        confidence=_confidence(),
        rationale=rationale,
        evidence_component_ids=(candidate.components[0].component_id,),
        evidence_association_ids=(candidate.associations[0].association_id,),
        evidence=(("basis", "caption_and_visual_evidence"),),
    )


def test__figure_relevance__completed_proposal_retains_exact_evidence() -> None:
    selection = _selection()
    request = _request(selection)
    proposal = _proposal(request)
    selection_result = FigureRelevanceSelectionResult.create(
        selection=selection,
        status=FigureRelevanceStatus.COMPLETED,
        proposal=proposal,
    )

    result = FigureRelevanceResult.create(
        request=request,
        processor_identity=_identity(),
        selection_results=(selection_result,),
    )

    assert proposal.level is FigureRelevanceLevel.PROPOSED_NECESSARY
    assert proposal.score.value == 0.91
    assert proposal.rationale
    assert result.request.selections[0].detection_result == (
        selection.detection_result
    )
    artifact = selection.detection_result.detection_input.page_evidence[
        0
    ].embedded_artifacts[0]
    assert artifact.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert result.cache_key == build_figure_relevance_cache_key(
        request, _identity()
    )


def test__figure_relevance__preserves_not_necessary_selection() -> None:
    first = _selection("figures", "first")
    second = _selection("image-only-page", "second")
    request = FigureRelevanceRequest.create(
        review_question="Which figures are necessary for this review?",
        selections=(first, second),
    )
    necessary = FigureRelevanceProposal.create(
        selection=first,
        configuration=request.configuration,
        score=_score(0.9),
        confidence=_confidence(),
        rationale="The captioned figure directly supports the question.",
    )
    not_necessary = FigureRelevanceProposal.create(
        selection=second,
        configuration=request.configuration,
        score=_score(0.1),
        confidence=_confidence(),
        rationale="The unlabeled image does not address the stated question.",
    )

    result = FigureRelevanceResult.create(
        request=request,
        processor_identity=_identity(),
        selection_results=(
            FigureRelevanceSelectionResult.create(
                selection=first,
                status=FigureRelevanceStatus.COMPLETED,
                proposal=necessary,
            ),
            FigureRelevanceSelectionResult.create(
                selection=second,
                status=FigureRelevanceStatus.COMPLETED,
                proposal=not_necessary,
            ),
        ),
    )

    assert tuple(item.selection_id for item in result.selection_results) == (
        first.selection_id,
        second.selection_id,
    )
    assert result.selection_results[1].proposal is not None
    assert result.selection_results[1].proposal.level is (
        FigureRelevanceLevel.PROPOSED_NOT_NECESSARY
    )
    assert result.request.selections[1].candidate == second.candidate


def test__figure_relevance__supports_partial_and_failed_outcomes() -> None:
    selection = _selection(suffix="outcomes")
    request = _request(selection)
    warning = FigureRelevanceWarning.create(
        selection_id=selection.selection_id,
        code="figure_relevance.confidence_unavailable",
        severity=WarningSeverity.WARNING,
        message="The backend did not provide calibrated confidence.",
    )
    failure = FigureRelevanceFailure.create(
        selection_id=selection.selection_id,
        kind=FigureRelevanceFailureKind.OUTPUT_INCOMPLETE,
        message="Component-level evidence coverage was incomplete.",
        retryable=True,
    )
    proposal = FigureRelevanceProposal.create(
        selection=selection,
        configuration=request.configuration,
        score=_score(0.55),
        confidence=None,
        rationale="The figure may provide useful supporting context.",
    )

    with pytest.raises(ValueError, match="confidence requires a warning"):
        FigureRelevanceSelectionResult.create(
            selection=selection,
            status=FigureRelevanceStatus.COMPLETED,
            proposal=proposal,
        )
    partial = FigureRelevanceSelectionResult.create(
        selection=selection,
        status=FigureRelevanceStatus.PARTIAL,
        proposal=proposal,
        warnings=(warning,),
        failures=(failure,),
    )
    failed = FigureRelevanceSelectionResult.create(
        selection=selection,
        status=FigureRelevanceStatus.FAILED,
        proposal=None,
        failures=(
            FigureRelevanceFailure.create(
                selection_id=selection.selection_id,
                kind=FigureRelevanceFailureKind.STALE_INPUT,
                message="The selected figure evidence became stale.",
                retryable=True,
            ),
        ),
    )

    assert partial.proposal is not None
    assert partial.proposal.level is FigureRelevanceLevel.PROPOSED_SUPPORTING
    assert partial.proposal.confidence is None
    assert failed.proposal is None
    assert failed.failures[0].kind is FigureRelevanceFailureKind.STALE_INPUT


def test__figure_relevance__cache_identity_covers_all_inputs() -> None:
    selection = _selection(suffix="cache")
    request = _request(selection)
    baseline = build_figure_relevance_cache_key(request, _identity())
    changed_question = build_figure_relevance_cache_key(
        _request(selection, question="A different review question?"),
        _identity(),
    )
    changed_configuration = build_figure_relevance_cache_key(
        _request(
            selection,
            configuration=FigureRelevanceConfiguration(
                necessary_score_threshold=0.85
            ),
        ),
        _identity(),
    )
    changed_resource = build_figure_relevance_cache_key(
        request, _identity("model-v2")
    )
    changed_backend = build_figure_relevance_cache_key(
        request,
        replace(_identity(), backend_version="2"),
    )
    changed_candidate = build_figure_relevance_cache_key(
        _request(_selection("image-only-page", "cache-other")),
        _identity(),
    )

    assert (
        len(
            {
                baseline,
                changed_question,
                changed_configuration,
                changed_resource,
                changed_backend,
                changed_candidate,
            }
        )
        == 6
    )


def test__figure_relevance__rejects_unknown_and_incomplete_results() -> None:
    selection = _selection(suffix="validation")
    request = _request(selection)
    with pytest.raises(ValueError, match="unknown figure component"):
        FigureRelevanceProposal.create(
            selection=selection,
            configuration=request.configuration,
            score=_score(0.9),
            confidence=None,
            rationale="The evidence directly addresses the question.",
            evidence_component_ids=("unknown-component",),
        )
    with pytest.raises(ValueError, match="order or coverage"):
        FigureRelevanceResult.create(
            request=request,
            processor_identity=_identity(),
            selection_results=(),
        )


def test__figure_relevance__enforces_question_and_rationale_limits() -> None:
    selection = _selection(suffix="limits")
    configuration = FigureRelevanceConfiguration(
        max_question_characters=8,
        max_rationale_characters=8,
    )

    with pytest.raises(FigureRelevanceLimitError, match="review question"):
        _request(
            selection,
            question="This question is too long",
            configuration=configuration,
        )
    with pytest.raises(
        FigureRelevanceLimitError,
        match="max_input_artifact_bytes",
    ):
        _request(
            selection,
            configuration=FigureRelevanceConfiguration(
                max_input_artifact_bytes=1
            ),
        )

    with pytest.raises(FigureRelevanceLimitError, match="rationale"):
        FigureRelevanceProposal.create(
            selection=selection,
            configuration=configuration,
            score=_score(0.9),
            confidence=None,
            rationale="Too long rationale",
        )


def test__figure_relevance__contracts_are_immutable_and_reject_stale_ids() -> (
    None
):
    selection = _selection(suffix="immutable")
    request = _request(selection)
    proposal = _proposal(request)
    selection_result = FigureRelevanceSelectionResult.create(
        selection=selection,
        status=FigureRelevanceStatus.COMPLETED,
        proposal=proposal,
    )
    result = FigureRelevanceResult.create(
        request=request,
        processor_identity=_identity(),
        selection_results=(selection_result,),
    )

    with pytest.raises(FrozenInstanceError):
        proposal.rationale = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="selection ID is inconsistent"):
        replace(selection, selection_id="stale-selection")
    with pytest.raises(ValueError, match="request ID is inconsistent"):
        replace(request, review_question="Changed question")
    with pytest.raises(ValueError, match="proposal ID is inconsistent"):
        replace(proposal, rationale="Changed rationale")
    with pytest.raises(ValueError, match="result ID is inconsistent"):
        replace(result, result_id="figure-relevance-result:sha256:" + "0" * 64)


def test__figure_relevance__processor_protocol_is_engine_neutral() -> None:
    selection = _selection(suffix="protocol")
    request = _request(selection)

    class StaticProcessor:
        name = "static-figure-relevance"
        version = "1"

        def identity_for(
            self, _request: FigureRelevanceRequest
        ) -> FigureRelevanceProcessorIdentity:
            return _identity()

        def process(
            self, actual_request: FigureRelevanceRequest
        ) -> FigureRelevanceResult:
            proposal = _proposal(actual_request)
            return FigureRelevanceResult.create(
                request=actual_request,
                processor_identity=self.identity_for(actual_request),
                selection_results=(
                    FigureRelevanceSelectionResult.create(
                        selection=actual_request.selections[0],
                        status=FigureRelevanceStatus.COMPLETED,
                        proposal=proposal,
                    ),
                ),
            )

    processor: FigureRelevanceProcessor = StaticProcessor()
    result = processor.process(request)

    assert result.processor_identity == processor.identity_for(request)
    assert result.selection_results[0].proposal is not None
