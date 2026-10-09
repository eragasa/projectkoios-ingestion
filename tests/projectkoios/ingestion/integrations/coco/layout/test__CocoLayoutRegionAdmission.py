"""Generic per-category COCO region-admission tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.ingestion.integrations.coco.layout.admission.actionizer import (  # noqa: E501
    CocoLayoutRegionAdmissionActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.admission.configuration import (  # noqa: E501
    CocoLayoutRegionAdmissionConfiguration,
)
from projectkoios.ingestion.integrations.coco.layout.admission.evidence import (  # noqa: E501
    CocoLayoutRegionAdmissionDisposition,
)
from projectkoios.ingestion.integrations.coco.layout.admission.outcome import (  # noqa: E501
    CocoLayoutCategoryAdmissionStatus,
)
from projectkoios.ingestion.integrations.coco.layout.admission.request import (  # noqa: E501
    CocoLayoutRegionAdmissionRequest,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.actionizer import (  # noqa: E501
    CocoLayoutDetectorGateActionizer,
)
from projectkoios.ingestion.integrations.coco.layout.detector.gate.reason import (  # noqa: E501
    CocoLayoutDetectorGateStatus,
)

from tests.projectkoios.ingestion.integrations.coco.layout.detector_fixture import (  # noqa: E501
    coco_layout_gate_request,
)


def admission_request(
    *,
    include_limitations: bool = True,
    omit_formula: bool = False,
    duplicate_formula: bool = False,
    minimum_confidence: float = 0.5,
    duplicate_iou_threshold: float = 0.8,
    maximum_regions_per_category: int = 256,
) -> CocoLayoutRegionAdmissionRequest:
    """Build exact detector/proposal evidence without page-gate authority."""
    gate_request = coco_layout_gate_request(
        include_limitations=include_limitations,
        omit_formula=omit_formula,
        duplicate_formula=duplicate_formula,
    )
    profile = gate_request.parsing_result.detector_result.request.configuration.profile  # type: ignore[union-attr]  # noqa: E501
    return CocoLayoutRegionAdmissionRequest(
        parsing_result=gate_request.parsing_result,
        proposal_result=gate_request.proposal_result,
        configuration=CocoLayoutRegionAdmissionConfiguration(
            profile=profile,
            minimum_confidence=minimum_confidence,
            duplicate_iou_threshold=duplicate_iou_threshold,
            maximum_regions_per_category=maximum_regions_per_category,
        ),
    )


def test_region_admission_is_independent_of_page_finalization() -> None:
    gate_request = coco_layout_gate_request(
        include_limitations=True,
        duplicate_formula=True,
    )
    page_gate = CocoLayoutDetectorGateActionizer().action(request=gate_request)
    result = CocoLayoutRegionAdmissionActionizer().action(
        request=admission_request(duplicate_formula=True)
    )

    assert page_gate.status is CocoLayoutDetectorGateStatus.ESCALATION_REQUIRED
    assert len(result.category_outcomes) == 11
    assert len(result.limitations) == 2

    formula = result.require_category(3)
    formula_evidence = tuple(formula.evidence)
    assert formula.status is CocoLayoutCategoryAdmissionStatus.ADMITTED
    assert [item.disposition for item in formula_evidence] == [
        CocoLayoutRegionAdmissionDisposition.ADMITTED,
        CocoLayoutRegionAdmissionDisposition.EXCLUDED_DUPLICATE,
    ]
    assert len(formula.admitted_adaptations) == 1

    text = result.require_category(10)
    assert text.status is CocoLayoutCategoryAdmissionStatus.ADMITTED
    assert len(text.admitted_adaptations) == 1


def test_region_admission_covers_empty_profile_categories() -> None:
    result = CocoLayoutRegionAdmissionActionizer().action(
        request=admission_request(omit_formula=True)
    )

    formula = result.require_category(3)
    assert formula.status is CocoLayoutCategoryAdmissionStatus.EMPTY
    assert len(formula.evidence) == 0
    assert len(formula.admitted_adaptations) == 0


def test_region_admission_applies_scoped_confidence() -> None:
    result = CocoLayoutRegionAdmissionActionizer().action(
        request=admission_request(minimum_confidence=0.95)
    )

    formula = result.require_category(3)
    assert formula.status is CocoLayoutCategoryAdmissionStatus.EMPTY
    assert tuple(item.disposition for item in formula.evidence) == (
        CocoLayoutRegionAdmissionDisposition.EXCLUDED_BELOW_CONFIDENCE,
    )
    assert result.require_category(10).status is (
        CocoLayoutCategoryAdmissionStatus.ADMITTED
    )


def test_region_admission_escalates_only_overflowing_category() -> None:
    result = CocoLayoutRegionAdmissionActionizer().action(
        request=admission_request(
            duplicate_formula=True,
            duplicate_iou_threshold=1.0,
            maximum_regions_per_category=1,
        )
    )

    formula = result.require_category(3)
    assert formula.status is (
        CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED
    )
    assert len(formula.admitted_adaptations) == 0
    assert all(
        item.disposition
        is CocoLayoutRegionAdmissionDisposition.ESCALATION_REQUIRED_LIMIT
        for item in formula.evidence
    )
    assert result.require_category(10).status is (
        CocoLayoutCategoryAdmissionStatus.ADMITTED
    )


def test_region_admission_rejects_proposal_lineage_drift() -> None:
    exact = admission_request()
    other = admission_request(duplicate_formula=True)

    with pytest.raises(ValueError, match="exact detector result"):
        replace(exact, proposal_result=other.proposal_result)


def test_region_admission_result_rejects_forged_evidence() -> None:
    result = CocoLayoutRegionAdmissionActionizer().action(
        request=admission_request()
    )
    other = CocoLayoutRegionAdmissionActionizer().action(
        request=admission_request(include_limitations=False)
    )

    with pytest.raises(ValueError, match="deterministic request derivation"):
        replace(result, limitations=other.limitations)
