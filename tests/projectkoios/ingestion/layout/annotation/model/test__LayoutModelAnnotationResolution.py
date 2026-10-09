from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.layout.annotation.collection import (
    LayoutAnnotationCollection,
)
from projectkoios.ingestion.layout.annotation.human.evidence import (
    LayoutHumanFinalReviewEvidence,
    LayoutHumanFinalReviewStatus,
)
from projectkoios.ingestion.layout.annotation.kind import (
    LayoutAnnotationOutcome,
)
from projectkoios.ingestion.layout.annotation.model.configuration import (
    LayoutAnnotationModelConfiguration,
)
from projectkoios.ingestion.layout.annotation.model.invocation import (
    LayoutAnnotationModelInvocationFailureKind,
    LayoutAnnotationModelInvocationResult,
    LayoutAnnotationModelInvocationStatus,
)
from projectkoios.ingestion.layout.annotation.model.limitation import (
    LayoutModelAnnotationLimitation,
    LayoutModelAnnotationLimitationCode,
)
from projectkoios.ingestion.layout.annotation.model.parsing.actionizer import (
    LayoutModelResponseParser,
)
from projectkoios.ingestion.layout.annotation.model.parsing.request import (
    LayoutModelResponseParsingRequest,
)
from projectkoios.ingestion.layout.annotation.model.parsing.result import (
    LayoutModelResponseParsingResult,
)
from projectkoios.ingestion.layout.annotation.model.parsing.status import (
    LayoutModelResponseParsingStatus,
)
from projectkoios.ingestion.layout.annotation.model.prompt import (
    LayoutAnnotationModelPrompt,
)
from projectkoios.ingestion.layout.annotation.model.request import (
    LayoutAnnotationModelRequest,
)
from projectkoios.ingestion.layout.annotation.model.resolution.actionizer import (  # noqa: E501
    LayoutModelAnnotationResolutionActionizer,
)
from projectkoios.ingestion.layout.annotation.model.resolution.policy import (
    LayoutModelAnnotationResolutionPolicy,
)
from projectkoios.ingestion.layout.annotation.model.resolution.request import (
    LayoutModelAnnotationResolutionRequest,
)
from projectkoios.ingestion.layout.annotation.model.resolution.result import (
    LayoutModelAnnotationResolutionResult,
    LayoutModelAnnotationResolutionStatus,
)
from projectkoios.ingestion.layout.annotation.model.resource import (
    LayoutAnnotationModelResource,
)
from projectkoios.ingestion.layout.annotation.region import (
    LayoutRegionAnnotation,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.review.actionizer import (
    DeterministicLayoutReviewActionizer,
)
from projectkoios.ingestion.layout.review.configuration import (
    LayoutReviewConfiguration,
)
from projectkoios.ingestion.layout.review.request import LayoutReviewRequest
from projectkoios.ingestion.layout.review.result import LayoutReviewCase
from projectkoios.ingestion.sha256.hash import SHA256Hash

from tests.projectkoios.ingestion.layout.review.layout_review_support import (
    LayoutReviewFixture,
)


def model_resource() -> LayoutAnnotationModelResource:
    return LayoutAnnotationModelResource(
        provider_name="fixture-provider",
        model_name="fixture-vision-model",
        model_version="1",
        model_sha256=SHA256Hash("c" * 64),
        runtime_name="fixture-runtime",
        runtime_version="1",
    )


def model_response(
    case: LayoutReviewCase,
    *,
    outcome: str = "no_failure_observed",
    regions: list[object] | None = None,
    order_edges: list[object] | None = None,
    failures: list[object] | None = None,
) -> str:
    return CanonicalJsonSerializer.serialize_text(
        {
            "schema_version": 1,
            "case_id": case.case_id,
            "outcome": outcome,
            "regions": regions or [],
            "order_edges": order_edges or [],
            "failures": failures or [],
        }
    )


def model_invocation(
    case: LayoutReviewCase,
    replica_index: int,
    response: str | bytes | None,
    *,
    resource: LayoutAnnotationModelResource | None = None,
    image_byte_length: int = 128,
    configuration: LayoutAnnotationModelConfiguration | None = None,
    failed: bool = False,
) -> LayoutAnnotationModelInvocationResult:
    prompt = LayoutAnnotationModelPrompt.create(case=case)
    request = LayoutAnnotationModelRequest(
        case=case,
        resource=resource or model_resource(),
        image=ManagedArtifactReference(
            sha256=case.request.render.image_sha256,
            byte_length=image_byte_length,
            media_type=ManagedArtifactMediaType.IMAGE_PNG,
        ),
        prompt=prompt,
        configuration=configuration or LayoutAnnotationModelConfiguration(),
        replica_index=replica_index,
    )
    return LayoutAnnotationModelInvocationResult(
        request=request,
        status=(
            LayoutAnnotationModelInvocationStatus.FAILED
            if failed
            else LayoutAnnotationModelInvocationStatus.COMPLETE
        ),
        request_document_bytes=request.document_bytes(),
        raw_response_bytes=(
            response
            if isinstance(response, bytes) or response is None
            else response.encode("utf-8")
        ),
        failure_kind=(
            LayoutAnnotationModelInvocationFailureKind.TRANSPORT
            if failed
            else None
        ),
        failure_code="fixture_transport_failure" if failed else None,
    )


def parsing_result(
    case: LayoutReviewCase,
    replica_index: int,
    response: str | bytes,
    *,
    resource: LayoutAnnotationModelResource | None = None,
    image_byte_length: int = 128,
    configuration: LayoutAnnotationModelConfiguration | None = None,
) -> LayoutModelResponseParsingResult:
    invocation = model_invocation(
        case,
        replica_index,
        response,
        resource=resource,
        image_byte_length=image_byte_length,
        configuration=configuration,
    )
    return LayoutModelResponseParser().action(
        request=LayoutModelResponseParsingRequest(invocation=invocation)
    )


def resolution_request(
    case: LayoutReviewCase,
    responses: tuple[str, str, str],
) -> LayoutModelAnnotationResolutionRequest:
    return LayoutModelAnnotationResolutionRequest(
        case=case,
        policy=LayoutModelAnnotationResolutionPolicy(),
        parsing_results=tuple(
            parsing_result(case, index, response)
            for index, response in enumerate(responses)
        ),
    )


def test__prompt_and_invocation_retain_exact_lineage() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    prompt = LayoutAnnotationModelPrompt.create(case=case)

    result = parsing_result(case, 0, model_response(case))

    assert prompt == LayoutAnnotationModelPrompt.create(case=case)
    assert case.case_id in prompt.text
    assert case.request.render.image_sha256 in prompt.text
    assert result.status is LayoutModelResponseParsingStatus.PARSED
    assert result.request.invocation.raw_response_bytes == model_response(
        case
    ).encode("utf-8")
    assert result.request.invocation.request.resource.model_sha256 == "c" * 64
    assert result.request.invocation.request.prompt == prompt
    assert (
        result.request.invocation.request_document_bytes
        == result.request.invocation.request.document_bytes()
    )
    assert result.request.invocation.request_document_byte_length > 0
    with pytest.raises(ValueError, match="differs from render evidence"):
        replace(
            result.request.invocation.request,
            image=ManagedArtifactReference(
                sha256=SHA256Hash("d" * 64),
                byte_length=128,
                media_type=ManagedArtifactMediaType.IMAGE_PNG,
            ),
        )


def test__invocation_rejects_substituted_request_document() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    parsed = parsing_result(case, 0, model_response(case))
    invocation = parsed.request.invocation

    with pytest.raises(ValueError, match="differs from the request"):
        replace(invocation, request_document_bytes=b"{}")


def test__parser_rejects_malformed_utf8() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()

    result = parsing_result(case, 0, b"{\xff}")

    assert result.status is LayoutModelResponseParsingStatus.REJECTED
    assert result.limitation is not None
    assert result.limitation.code.value == "malformed_json"


def test__parser_rejects_duplicate_fields_and_unknown_fields() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    duplicate = (
        '{"schema_version":1,"schema_version":1,"case_id":"'
        + case.case_id
        + '","outcome":"no_failure_observed","regions":[],'
        '"order_edges":[],"failures":[]}'
    )
    unknown = CanonicalJsonSerializer.serialize_text(
        {
            "schema_version": 1,
            "case_id": case.case_id,
            "outcome": "no_failure_observed",
            "regions": [],
            "order_edges": [],
            "failures": [],
            "extra": True,
        }
    )

    duplicate_result = parsing_result(case, 0, duplicate)
    unknown_result = parsing_result(case, 0, unknown)

    assert duplicate_result.status is LayoutModelResponseParsingStatus.REJECTED
    assert duplicate_result.limitation is not None
    assert duplicate_result.limitation.code.value == "malformed_json"
    assert unknown_result.status is LayoutModelResponseParsingStatus.REJECTED
    assert unknown_result.limitation is not None
    assert unknown_result.limitation.code.value == "invalid_schema"


def test__parser_rejects_unknown_evidence_references() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    response = model_response(
        case,
        outcome="correction_proposed",
        regions=[
            {
                "kind": "text",
                "bounding_box_pixels": [1.0, 1.0, 10.0, 10.0],
                "block_ids": ["unknown-block"],
            }
        ],
    )

    result = parsing_result(case, 0, response)

    assert result.status is LayoutModelResponseParsingStatus.REJECTED
    assert result.limitation is not None
    assert result.limitation.code.value == "invalid_annotation"


def test__parser_classifies_adversarial_failures_exactly() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    first_block_id, second_block_id = (
        review.block_id for review in case.block_reviews[:2]
    )
    valid_region = {
        "kind": "text",
        "bounding_box_pixels": [1.0, 1.0, 10.0, 10.0],
        "block_ids": [first_block_id],
    }
    duplicate_edge = {
        "before_block_id": first_block_id,
        "after_block_id": second_block_id,
    }
    valid_failure = {
        "kind": "block_assignment",
        "block_ids": [first_block_id],
        "proposal_ids": [case.proposal_ids[0]],
        "region_indexes": [],
    }
    base = model_response(case)
    cases = (
        (
            "trailing output",
            base + " trailing",
            LayoutModelAnnotationLimitationCode.MALFORMED_JSON,
        ),
        (
            "unknown vocabulary",
            model_response(case, outcome="unknown"),
            LayoutModelAnnotationLimitationCode.INVALID_SCHEMA,
        ),
        (
            "non-finite number",
            base.replace(
                '"regions":[]',
                '"regions":[{"kind":"text",'
                '"bounding_box_pixels":[0,0,NaN,1],'
                f'"block_ids":["{first_block_id}"]}}]',
            ),
            LayoutModelAnnotationLimitationCode.MALFORMED_JSON,
        ),
        (
            "excessive depth",
            base.replace('"regions":[]', '"regions":' + "[" * 20 + "]" * 20),
            LayoutModelAnnotationLimitationCode.MALFORMED_JSON,
        ),
        (
            "excessive string",
            model_response(
                case,
                outcome="correction_proposed",
                regions=[{**valid_region, "block_ids": ["x" * 64_001]}],
            ),
            LayoutModelAnnotationLimitationCode.MALFORMED_JSON,
        ),
        (
            "out-of-bounds geometry",
            model_response(
                case,
                outcome="correction_proposed",
                regions=[
                    {
                        **valid_region,
                        "bounding_box_pixels": [
                            1.0,
                            1.0,
                            case.image_width + 1.0,
                            10.0,
                        ],
                    }
                ],
            ),
            LayoutModelAnnotationLimitationCode.INVALID_ANNOTATION,
        ),
        (
            "unknown proposal",
            model_response(
                case,
                outcome="failure_observed",
                failures=[
                    {**valid_failure, "proposal_ids": ["unknown-proposal"]}
                ],
            ),
            LayoutModelAnnotationLimitationCode.INVALID_ANNOTATION,
        ),
        (
            "unknown region index",
            model_response(
                case,
                outcome="failure_observed",
                failures=[{**valid_failure, "region_indexes": [0]}],
            ),
            LayoutModelAnnotationLimitationCode.INVALID_SCHEMA,
        ),
        (
            "duplicate region",
            model_response(
                case,
                outcome="correction_proposed",
                regions=[valid_region, valid_region],
            ),
            LayoutModelAnnotationLimitationCode.INVALID_ANNOTATION,
        ),
        (
            "duplicate order edge",
            model_response(
                case,
                outcome="correction_proposed",
                order_edges=[duplicate_edge, duplicate_edge],
            ),
            LayoutModelAnnotationLimitationCode.INVALID_ANNOTATION,
        ),
        (
            "cyclic order",
            model_response(
                case,
                outcome="correction_proposed",
                order_edges=[
                    duplicate_edge,
                    {
                        "before_block_id": second_block_id,
                        "after_block_id": first_block_id,
                    },
                ],
            ),
            LayoutModelAnnotationLimitationCode.INVALID_ANNOTATION,
        ),
        (
            "inconsistent outcome",
            model_response(case, regions=[valid_region]),
            LayoutModelAnnotationLimitationCode.INVALID_ANNOTATION,
        ),
    )

    for label, response, expected_code in cases:
        result = parsing_result(case, 0, response)
        assert result.status is LayoutModelResponseParsingStatus.REJECTED, label
        assert result.limitation is not None, label
        assert result.limitation.code is expected_code, label


def test__parsing_result_rejects_candidate_substitution() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    honest = parsing_result(case, 0, model_response(case))
    conflict = parsing_result(
        case,
        1,
        model_response(
            case,
            outcome="failure_observed",
            failures=[
                {
                    "kind": "block_assignment",
                    "block_ids": [case.block_reviews[0].block_id],
                    "proposal_ids": [case.proposal_ids[0]],
                    "region_indexes": [],
                }
            ],
        ),
    )
    assert conflict.candidate is not None

    with pytest.raises(ValueError, match="exact raw response interpretation"):
        LayoutModelResponseParsingResult(
            request=honest.request,
            status=LayoutModelResponseParsingStatus.PARSED,
            candidate=conflict.candidate,
            limitation=None,
        )


def test__parsing_result_rejects_parsed_claim_over_malformed_bytes() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    candidate_result = parsing_result(case, 0, model_response(case))
    malformed = parsing_result(case, 1, b"{\xff}")
    assert candidate_result.candidate is not None

    with pytest.raises(ValueError, match="exact raw response interpretation"):
        LayoutModelResponseParsingResult(
            request=malformed.request,
            status=LayoutModelResponseParsingStatus.PARSED,
            candidate=candidate_result.candidate,
            limitation=None,
        )


def test__parser_classifies_failed_invocation_exactly() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    invocation = model_invocation(case, 0, None, failed=True)

    result = LayoutModelResponseParser().action(
        request=LayoutModelResponseParsingRequest(invocation=invocation)
    )

    assert result.status is LayoutModelResponseParsingStatus.REJECTED
    assert result.limitation is not None
    assert (
        result.limitation.code
        is LayoutModelAnnotationLimitationCode.INVOCATION_FAILED
    )


def test__parsing_result_rejects_incorrect_limitation_classifications() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    unknown = CanonicalJsonSerializer.serialize_text(
        {
            "schema_version": 1,
            "case_id": case.case_id,
            "outcome": "no_failure_observed",
            "regions": [],
            "order_edges": [],
            "failures": [],
            "extra": True,
        }
    )
    invalid_annotation = model_response(
        case,
        outcome="correction_proposed",
        regions=[
            {
                "kind": "text",
                "bounding_box_pixels": [1.0, 1.0, 10.0, 10.0],
                "block_ids": ["unknown-block"],
            }
        ],
    )
    invocations_and_wrong_codes = (
        (
            model_invocation(case, 0, None, failed=True),
            LayoutModelAnnotationLimitationCode.MALFORMED_JSON,
        ),
        (
            model_invocation(case, 0, b"{\xff}"),
            LayoutModelAnnotationLimitationCode.INVOCATION_FAILED,
        ),
        (
            model_invocation(case, 0, unknown),
            LayoutModelAnnotationLimitationCode.MALFORMED_JSON,
        ),
        (
            model_invocation(case, 0, invalid_annotation),
            LayoutModelAnnotationLimitationCode.INVALID_SCHEMA,
        ),
    )

    for invocation, wrong_code in invocations_and_wrong_codes:
        request = LayoutModelResponseParsingRequest(invocation=invocation)
        limitation = LayoutModelAnnotationLimitation(
            case_id=case.case_id,
            code=wrong_code,
            affected_invocation_ids=(invocation.invocation_id,),
        )
        with pytest.raises(
            ValueError, match="exact raw response interpretation"
        ):
            LayoutModelResponseParsingResult(
                request=request,
                status=LayoutModelResponseParsingStatus.REJECTED,
                candidate=None,
                limitation=limitation,
            )


def test__resolution_admits_agreement_despite_one_parse_failure() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    response = model_response(case)
    equivalent_response = "\n  " + response + "\n"
    request = resolution_request(
        case,
        (response, equivalent_response, "not-json"),
    )

    result = LayoutModelAnnotationResolutionActionizer().action(request=request)

    assert result.status is LayoutModelAnnotationResolutionStatus.ADMITTED
    assert result.candidate is not None
    assert len(result.agreeing_invocation_ids) == 2
    assert len(set(result.agreeing_invocation_ids)) == 2
    assert result.limitation is None


def test__resolution_admits_semantic_array_permutations() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    first_block_id, second_block_id = (
        review.block_id for review in case.block_reviews[:2]
    )
    first_region = {
        "kind": "text",
        "bounding_box_pixels": [1.0, 1.0, 10.0, 10.0],
        "block_ids": [first_block_id, second_block_id],
    }
    second_region = {
        "kind": "text",
        "bounding_box_pixels": [11.0, 1.0, 20.0, 10.0],
        "block_ids": [second_block_id],
    }
    first = model_response(
        case,
        outcome="correction_proposed",
        regions=[first_region, second_region],
    )
    second = model_response(
        case,
        outcome="correction_proposed",
        regions=[
            second_region,
            {**first_region, "block_ids": [second_block_id, first_block_id]},
        ],
    )

    result = LayoutModelAnnotationResolutionActionizer().action(
        request=resolution_request(case, (first, second, "not-json"))
    )

    assert result.status is LayoutModelAnnotationResolutionStatus.ADMITTED
    assert len(result.agreeing_invocation_ids) == 2


def test__resolution_rejects_conflicting_valid_candidate() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    block_id = case.block_reviews[0].block_id
    proposal_id = case.proposal_ids[0]
    agreement = model_response(case)
    conflict = model_response(
        case,
        outcome="failure_observed",
        failures=[
            {
                "kind": "block_assignment",
                "block_ids": [block_id],
                "proposal_ids": [proposal_id],
                "region_indexes": [],
            }
        ],
    )
    request = resolution_request(case, (agreement, agreement, conflict))

    result = LayoutModelAnnotationResolutionActionizer().action(request=request)

    assert result.status is LayoutModelAnnotationResolutionStatus.UNRESOLVED
    assert result.candidate is None
    assert result.limitation is not None
    assert result.limitation.code.value == "conflicting_valid_responses"


def test__resolution_request_rejects_replica_lineage_mismatches() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    response = model_response(case)
    ordinary = tuple(
        parsing_result(case, index, response) for index in range(3)
    )

    invalid_sets = (
        (
            "ordered by complete replica index",
            (ordinary[1], ordinary[0], ordinary[2]),
        ),
        (
            "ordered by complete replica index",
            (ordinary[0], ordinary[0], ordinary[2]),
        ),
        (
            "share model, image, prompt, and configuration",
            (
                ordinary[0],
                parsing_result(
                    case,
                    1,
                    response,
                    resource=LayoutAnnotationModelResource(
                        provider_name="fixture-provider",
                        model_name="fixture-vision-model",
                        model_version="2",
                        model_sha256=SHA256Hash("d" * 64),
                        runtime_name="fixture-runtime",
                        runtime_version="1",
                    ),
                ),
                ordinary[2],
            ),
        ),
        (
            "share model, image, prompt, and configuration",
            (
                ordinary[0],
                parsing_result(case, 1, response, image_byte_length=129),
                ordinary[2],
            ),
        ),
        (
            "share model, image, prompt, and configuration",
            (
                ordinary[0],
                parsing_result(
                    case,
                    1,
                    response,
                    configuration=LayoutAnnotationModelConfiguration(
                        temperature=0.5
                    ),
                ),
                ordinary[2],
            ),
        ),
    )

    for message, parsing_results in invalid_sets:
        with pytest.raises(ValueError, match=message):
            LayoutModelAnnotationResolutionRequest(
                case=case,
                policy=LayoutModelAnnotationResolutionPolicy(),
                parsing_results=parsing_results,
            )


def test__resolution_request_rejects_another_case() -> None:
    _, _, review_request, case = LayoutReviewFixture().prepared_case()
    different_request = LayoutReviewRequest.create(
        layout=review_request.layout,
        render=review_request.render,
        proposal_source=review_request.proposal_source,
        proposals=review_request.proposals,
        configuration=LayoutReviewConfiguration(
            minimum_block_intersection_ratio=0.6,
            minimum_page_coverage_ratio=0.9,
        ),
    )
    different_case = DeterministicLayoutReviewActionizer().action(
        request=different_request
    )
    response = model_response(different_case)
    results = tuple(
        parsing_result(different_case, index, response) for index in range(3)
    )

    with pytest.raises(ValueError, match="bind the exact case"):
        LayoutModelAnnotationResolutionRequest(
            case=case,
            policy=LayoutModelAnnotationResolutionPolicy(),
            parsing_results=results,
        )


def test__resolution_request_requires_exact_configured_replica_count() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    response = model_response(case)

    with pytest.raises(ValueError, match="exact required result count"):
        LayoutModelAnnotationResolutionRequest(
            case=case,
            policy=LayoutModelAnnotationResolutionPolicy(),
            parsing_results=(
                parsing_result(case, 0, response),
                parsing_result(case, 1, response),
            ),
        )


def test__one_response_cannot_satisfy_resolution_policy() -> None:
    with pytest.raises(ValueError, match="between 2 and 16"):
        LayoutModelAnnotationResolutionPolicy(
            required_response_count=1,
            minimum_agreement_count=1,
        )


def test__resolution_result_rejects_forged_agreement_subset() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    response = model_response(case)
    request = resolution_request(case, (response, response, response))
    resolved = LayoutModelAnnotationResolutionActionizer().action(
        request=request
    )
    assert resolved.candidate is not None

    with pytest.raises(ValueError, match="sufficient exact agreement"):
        LayoutModelAnnotationResolutionResult(
            request=request,
            status=LayoutModelAnnotationResolutionStatus.ADMITTED,
            candidate=resolved.candidate,
            agreeing_invocation_ids=resolved.agreeing_invocation_ids[:2],
            limitation=None,
        )


def test__unresolved_result_rejects_incorrect_derived_limitation() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    response = model_response(case)
    conflict = model_response(
        case,
        outcome="failure_observed",
        failures=[
            {
                "kind": "block_assignment",
                "block_ids": [case.block_reviews[0].block_id],
                "proposal_ids": [case.proposal_ids[0]],
                "region_indexes": [],
            }
        ],
    )
    request = resolution_request(case, (response, response, conflict))
    limitation = LayoutModelAnnotationLimitation(
        case_id=case.case_id,
        code=(LayoutModelAnnotationLimitationCode.INSUFFICIENT_VALID_RESPONSES),
        affected_invocation_ids=tuple(
            item.invocation_id for item in request.parsing_results
        ),
    )

    with pytest.raises(ValueError, match="derived full-set limitation"):
        LayoutModelAnnotationResolutionResult(
            request=request,
            status=LayoutModelAnnotationResolutionStatus.UNRESOLVED,
            candidate=None,
            agreeing_invocation_ids=(),
            limitation=limitation,
        )


def test__human_review_states_are_explicit_separate_and_append_only() -> None:
    _, _, _, case = LayoutReviewFixture().prepared_case()
    response = model_response(case)
    resolution = LayoutModelAnnotationResolutionActionizer().action(
        request=resolution_request(case, (response, response, response))
    )
    not_reviewed = LayoutHumanFinalReviewEvidence(
        resolution=resolution,
        status=LayoutHumanFinalReviewStatus.NOT_HUMAN_REVIEWED,
    )
    affirmed = LayoutHumanFinalReviewEvidence(
        resolution=resolution,
        status=LayoutHumanFinalReviewStatus.AFFIRMED,
        reviewer_id="reviewer:fixture",
        review_protocol_id="protocol:layout-final-v1",
    )
    region = LayoutRegionAnnotation.create(
        case_id=case.case_id,
        kind=LayoutRegionKind.TEXT,
        bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
        block_ids=(case.block_reviews[0].block_id,),
    )
    correction = LayoutAnnotationCollection.create(
        case=case,
        annotator_id="reviewer:fixture",
        outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
        regions=(region,),
    )
    corrected = LayoutHumanFinalReviewEvidence(
        resolution=resolution,
        status=LayoutHumanFinalReviewStatus.CORRECTED,
        reviewer_id="reviewer:fixture",
        review_protocol_id="protocol:layout-final-v1",
        correction=correction,
    )
    rejected = LayoutHumanFinalReviewEvidence(
        resolution=resolution,
        status=LayoutHumanFinalReviewStatus.REJECTED,
        reviewer_id="reviewer:fixture",
        review_protocol_id="protocol:layout-final-v1",
    )

    assert not not_reviewed.is_terminal
    assert (
        affirmed.is_terminal and corrected.is_terminal and rejected.is_terminal
    )
    assert (
        len(
            {
                not_reviewed.review_id,
                affirmed.review_id,
                corrected.review_id,
                rejected.review_id,
            }
        )
        == 4
    )
    assert resolution.candidate is not None
    assert (
        resolution.candidate.outcome
        is LayoutAnnotationOutcome.NO_FAILURE_OBSERVED
    )
    with pytest.raises(ValueError, match="cannot claim a human decision"):
        replace(not_reviewed, reviewer_id="reviewer:fixture")


def test__human_review_rejects_invalid_terminal_evidence() -> None:
    _, _, review_request, case = LayoutReviewFixture().prepared_case()
    response = model_response(case)
    resolution = LayoutModelAnnotationResolutionActionizer().action(
        request=resolution_request(case, (response, response, response))
    )
    unresolved = LayoutModelAnnotationResolutionActionizer().action(
        request=resolution_request(
            case,
            ("not-json", "still-not-json", "also-not-json"),
        )
    )
    region = LayoutRegionAnnotation.create(
        case_id=case.case_id,
        kind=LayoutRegionKind.TEXT,
        bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
        block_ids=(case.block_reviews[0].block_id,),
    )
    correction = LayoutAnnotationCollection.create(
        case=case,
        annotator_id="reviewer:fixture",
        outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
        regions=(region,),
    )
    wrong_reviewer = LayoutAnnotationCollection.create(
        case=case,
        annotator_id="reviewer:other",
        outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
        regions=(region,),
    )
    non_correction = LayoutAnnotationCollection.create(
        case=case,
        annotator_id="reviewer:fixture",
        outcome=LayoutAnnotationOutcome.NO_FAILURE_OBSERVED,
    )
    different_request = LayoutReviewRequest.create(
        layout=review_request.layout,
        render=review_request.render,
        proposal_source=review_request.proposal_source,
        proposals=review_request.proposals,
        configuration=LayoutReviewConfiguration(
            minimum_block_intersection_ratio=0.6,
            minimum_page_coverage_ratio=0.9,
        ),
    )
    different_case = DeterministicLayoutReviewActionizer().action(
        request=different_request
    )
    different_region = LayoutRegionAnnotation.create(
        case_id=different_case.case_id,
        kind=LayoutRegionKind.TEXT,
        bounding_box_pixels=(20.0, 20.0, 80.0, 40.0),
        block_ids=(different_case.block_reviews[0].block_id,),
    )
    wrong_case = LayoutAnnotationCollection.create(
        case=different_case,
        annotator_id="reviewer:fixture",
        outcome=LayoutAnnotationOutcome.CORRECTION_PROPOSED,
        regions=(different_region,),
    )

    with pytest.raises(ValueError, match="requires an admitted resolution"):
        LayoutHumanFinalReviewEvidence(
            resolution=unresolved,
            status=LayoutHumanFinalReviewStatus.NOT_HUMAN_REVIEWED,
        )
    with pytest.raises(ValueError):
        LayoutHumanFinalReviewEvidence(
            resolution=resolution,
            status=LayoutHumanFinalReviewStatus.AFFIRMED,
            review_protocol_id="protocol:layout-final-v1",
        )
    with pytest.raises(ValueError):
        LayoutHumanFinalReviewEvidence(
            resolution=resolution,
            status=LayoutHumanFinalReviewStatus.AFFIRMED,
            reviewer_id="reviewer:fixture",
        )
    for status in (
        LayoutHumanFinalReviewStatus.AFFIRMED,
        LayoutHumanFinalReviewStatus.REJECTED,
    ):
        with pytest.raises(ValueError, match="only corrected review"):
            LayoutHumanFinalReviewEvidence(
                resolution=resolution,
                status=status,
                reviewer_id="reviewer:fixture",
                review_protocol_id="protocol:layout-final-v1",
                correction=correction,
            )
    for invalid_correction in (
        None,
        wrong_reviewer,
        non_correction,
        wrong_case,
    ):
        with pytest.raises(ValueError, match="reviewer-authored case-bound"):
            LayoutHumanFinalReviewEvidence(
                resolution=resolution,
                status=LayoutHumanFinalReviewStatus.CORRECTED,
                reviewer_id="reviewer:fixture",
                review_protocol_id="protocol:layout-final-v1",
                correction=invalid_correction,
            )
