"""Fail-closed result semantics for the private layout-equation canary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.recognition.artifact import (
    EquationRecognitionArtifact,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
)
from projectkoios.ingestion.integrations.coco.layout.admission.outcome import (  # noqa: E501
    CocoLayoutCategoryAdmission,
    CocoLayoutCategoryAdmissionStatus,
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
from projectkoios.ingestion.integrations.coco.layout.equation.result import (
    CocoLayoutEquationProjectionResult,
)
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.sha256.hash import SHA256Hash

_CANARY_DOCUMENT_KEYS = frozenset(
    {
        "schema_version",
        "authority",
        "model_resource_id",
        "preprocessing_id",
        "preprocessing_original_size_order",
        "recognition_processor_identity",
        "page_results",
        "summary",
        "evidence_records",
    }
)
_PAGE_RESULT_KEYS = frozenset(
    {
        "case_id",
        "source_sha256",
        "page_index",
        "invocation_status",
        "parsing_status",
        "formula_admission_status",
        "accepted_formula_detection_count",
        "projection_status",
        "projection_candidate_count",
        "projection_exclusion_count",
        "assembly_status",
        "assembly_count",
        "recognition_status",
        "recognition_proposal_count",
        "recognition_proposed_count",
        "recognition_failed_count",
        "recognition_not_requested_count",
        "failure_code",
    }
)


class LayoutEquationCanaryStageStatus(StrEnum):
    """State whether one downstream canary stage completed or stopped."""

    COMPLETE = "complete"
    FAILED = "failed"
    NOT_EVALUATED = "not_evaluated"


class LayoutEquationCanaryBridgeStatus(StrEnum):
    """Aggregate bridge evaluation coverage without claiming correctness."""

    EVALUATED = "evaluated"
    PARTIALLY_EVALUATED = "partially_evaluated"
    NOT_EVALUATED = "not_evaluated"
    FAILED = "failed"


def require_formula_admission(
    result: CocoLayoutRegionAdmissionResult,
) -> CocoLayoutCategoryAdmission:
    """Return the unique formula-category admission from one exact result."""
    categories = tuple(
        category
        for category in result.request.configuration.profile.categories
        if category.kind is LayoutRegionKind.EQUATION
    )
    if len(categories) != 1:
        raise ValueError("canary requires one formula profile category")
    return result.require_category(categories[0].category_id)


@dataclass(frozen=True, slots=True)
class LayoutEquationCanaryDownstreamEvidence:
    """Typed downstream evidence, or an explicit category-admission stop."""

    admission_result: CocoLayoutRegionAdmissionResult
    projection: CocoLayoutEquationProjectionResult | None
    assembly: EquationAssemblyResult | None
    recognition: EquationRecognitionArtifact | None

    def __post_init__(self) -> None:
        if type(self.admission_result) is not CocoLayoutRegionAdmissionResult:
            raise TypeError(
                "admission_result must be exact typed admission evidence"
            )
        formula_admission = require_formula_admission(self.admission_result)
        values = (self.projection, self.assembly, self.recognition)
        if all(value is None for value in values):
            if (
                formula_admission.status
                is CocoLayoutCategoryAdmissionStatus.ADMITTED
            ):
                raise ValueError(
                    "admitted formula category requires downstream evidence"
                )
            return
        if type(self.projection) is not CocoLayoutEquationProjectionResult:
            raise TypeError("projection must be exact typed evidence")
        if type(self.assembly) is not EquationAssemblyResult:
            raise TypeError("assembly must be exact typed evidence")
        if type(self.recognition) is not EquationRecognitionArtifact:
            raise TypeError("recognition must be exact typed evidence")
        if self.projection.request.admission_result != self.admission_result:
            raise ValueError("projection differs from supplied admission")
        if self.assembly.detection_result_id != self.projection.result_id:
            raise ValueError("assembly differs from projected evidence")
        if self.recognition.assembly_artifact_id != self.assembly.artifact_id:
            raise ValueError("recognition differs from assembled evidence")


def execute_layout_equation_canary_downstream(
    *,
    admission_result: CocoLayoutRegionAdmissionResult,
    project: Callable[[], CocoLayoutEquationProjectionResult],
    assemble: Callable[
        [CocoLayoutEquationProjectionResult], EquationAssemblyResult
    ],
    recognize: Callable[[EquationAssemblyResult], EquationRecognitionArtifact],
) -> LayoutEquationCanaryDownstreamEvidence:
    """Execute downstream stages only for an admitted formula category."""
    if type(admission_result) is not CocoLayoutRegionAdmissionResult:
        raise TypeError(
            "admission_result must be exact typed admission evidence"
        )
    formula_admission = require_formula_admission(admission_result)
    if (
        formula_admission.status
        is not CocoLayoutCategoryAdmissionStatus.ADMITTED
    ):
        return LayoutEquationCanaryDownstreamEvidence(
            admission_result=admission_result,
            projection=None,
            assembly=None,
            recognition=None,
        )
    projection = project()
    if projection.request.admission_result != admission_result:
        raise ValueError("projection differs from supplied admission")
    assembly = assemble(projection)
    recognition = recognize(assembly)
    return LayoutEquationCanaryDownstreamEvidence(
        admission_result=admission_result,
        projection=projection,
        assembly=assembly,
        recognition=recognition,
    )


@dataclass(frozen=True, slots=True)
class LayoutEquationCanaryPageResult:
    """Retain fail-closed stage coverage for one exact private page."""

    case_id: str
    source_sha256: str
    page_index: int
    invocation_status: CocoLayoutDetectorInvocationStatus
    parsing_status: CocoLayoutDetectorOutputParsingStatus | None
    formula_admission_status: CocoLayoutCategoryAdmissionStatus | None
    accepted_formula_detection_count: int | None
    projection_status: LayoutEquationCanaryStageStatus
    projection_candidate_count: int | None
    projection_exclusion_count: int | None
    assembly_status: LayoutEquationCanaryStageStatus
    assembly_count: int | None
    recognition_status: LayoutEquationCanaryStageStatus
    recognition_proposal_count: int | None
    recognition_proposed_count: int | None
    recognition_failed_count: int | None
    recognition_not_requested_count: int | None
    failure_code: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise ValueError("case_id must be a non-empty string")
        if not SHA256Hash.is_canonical(self.source_sha256):
            raise ValueError("source_sha256 must be a canonical SHA-256")
        if (
            isinstance(self.page_index, bool)
            or not isinstance(self.page_index, int)
            or self.page_index < 0
        ):
            raise ValueError("page_index must be a non-negative integer")
        if not isinstance(
            self.invocation_status, CocoLayoutDetectorInvocationStatus
        ):
            raise TypeError("invocation_status uses an invalid enum")
        for name in (
            "projection_status",
            "assembly_status",
            "recognition_status",
        ):
            if not isinstance(
                getattr(self, name), LayoutEquationCanaryStageStatus
            ):
                raise TypeError(f"{name} uses an invalid enum")
        if self.failure_code is not None and (
            not isinstance(self.failure_code, str)
            or not self.failure_code.strip()
        ):
            raise ValueError("failure_code must be non-empty when present")
        if self.invocation_status is CocoLayoutDetectorInvocationStatus.FAILED:
            self._require_pre_projection_stop("failed invocation")
            if (
                self.parsing_status is not None
                or self.formula_admission_status is not None
            ):
                raise ValueError(
                    "failed invocation stops parsing and admission evaluation"
                )
            if self.accepted_formula_detection_count is not None:
                raise ValueError(
                    "failed invocation cannot report accepted formulas"
                )
            self._require_failure_code()
            return
        if self.parsing_status is None:
            raise ValueError("complete invocation requires parsing status")
        if not isinstance(
            self.parsing_status, CocoLayoutDetectorOutputParsingStatus
        ):
            raise TypeError("parsing_status uses an invalid enum")
        if self.parsing_status is CocoLayoutDetectorOutputParsingStatus.INVALID:
            self._require_pre_projection_stop("invalid parsing")
            if self.formula_admission_status is not None:
                raise ValueError("invalid parsing stops admission evaluation")
            if self.accepted_formula_detection_count is not None:
                raise ValueError(
                    "invalid parsing cannot report accepted formulas"
                )
            self._require_failure_code()
            return
        if not isinstance(
            self.formula_admission_status,
            CocoLayoutCategoryAdmissionStatus,
        ):
            raise TypeError("valid parsing requires formula admission status")
        self._require_count(
            "accepted_formula_detection_count",
            self.accepted_formula_detection_count,
        )
        if (
            self.formula_admission_status
            in (
                CocoLayoutCategoryAdmissionStatus.ADMITTED,
                CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED,
            )
            and self.accepted_formula_detection_count == 0
        ):
            raise ValueError(
                "admitted or escalated formula category requires a positive "
                "formula count"
            )
        if (
            self.formula_admission_status
            is CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED
        ):
            self._require_pre_projection_stop("formula admission escalation")
            self._require_failure_code()
            return
        if (
            self.formula_admission_status
            is CocoLayoutCategoryAdmissionStatus.EMPTY
        ):
            self._validate_empty_category_stages()
            return
        self._validate_admitted_stages()

    def _require_pre_projection_stop(self, reason: str) -> None:
        if self.projection_status is not (
            LayoutEquationCanaryStageStatus.NOT_EVALUATED
        ):
            raise ValueError(f"{reason} stops projection")
        if self.assembly_status is not (
            LayoutEquationCanaryStageStatus.NOT_EVALUATED
        ):
            raise ValueError(f"{reason} stops assembly")
        if self.recognition_status is not (
            LayoutEquationCanaryStageStatus.NOT_EVALUATED
        ):
            raise ValueError(f"{reason} stops recognition")
        if any(
            value is not None
            for value in (
                self.projection_candidate_count,
                self.projection_exclusion_count,
                self.assembly_count,
                self.recognition_proposal_count,
                self.recognition_proposed_count,
                self.recognition_failed_count,
                self.recognition_not_requested_count,
            )
        ):
            raise ValueError(f"{reason} cannot report downstream counts")

    def _validate_empty_category_stages(self) -> None:
        if self.accepted_formula_detection_count != 0:
            raise ValueError("empty formula admission cannot accept formulas")
        if any(
            status is not LayoutEquationCanaryStageStatus.COMPLETE
            for status in (
                self.projection_status,
                self.assembly_status,
                self.recognition_status,
            )
        ):
            raise ValueError("empty formula admission requires zero completion")
        if any(
            value != 0
            for value in (
                self.projection_candidate_count,
                self.projection_exclusion_count,
                self.assembly_count,
                self.recognition_proposal_count,
                self.recognition_proposed_count,
                self.recognition_failed_count,
                self.recognition_not_requested_count,
            )
        ):
            raise ValueError("empty formula admission requires zero counts")
        if self.failure_code is not None:
            raise ValueError("empty formula admission cannot carry failure")

    def _validate_admitted_stages(self) -> None:
        if self.projection_status is LayoutEquationCanaryStageStatus.FAILED:
            self._require_failed_stage_counts(
                stage="projection",
                counts=(
                    self.projection_candidate_count,
                    self.projection_exclusion_count,
                ),
            )
            self._require_downstream_not_evaluated("projection failure")
            self._require_failure_code()
            return
        if self.projection_status is not (
            LayoutEquationCanaryStageStatus.COMPLETE
        ):
            raise ValueError(
                "admitted formula category requires projection evaluation"
            )
        self._require_count(
            "projection_candidate_count", self.projection_candidate_count
        )
        self._require_count(
            "projection_exclusion_count", self.projection_exclusion_count
        )
        projection_candidate_count = self.projection_candidate_count
        projection_exclusion_count = self.projection_exclusion_count
        accepted_formula_count = self.accepted_formula_detection_count
        if (
            projection_candidate_count is None
            or projection_exclusion_count is None
            or accepted_formula_count is None
        ):
            raise AssertionError("validated projection count is absent")
        if (
            projection_candidate_count + projection_exclusion_count
            != accepted_formula_count
        ):
            raise ValueError(
                "projection candidates and exclusions must cover every "
                "accepted formula"
            )
        if self.assembly_status is LayoutEquationCanaryStageStatus.FAILED:
            self._require_failed_stage_counts(
                stage="assembly", counts=(self.assembly_count,)
            )
            if self.recognition_status is not (
                LayoutEquationCanaryStageStatus.NOT_EVALUATED
            ) or any(
                value is not None
                for value in (
                    self.recognition_proposal_count,
                    self.recognition_proposed_count,
                    self.recognition_failed_count,
                    self.recognition_not_requested_count,
                )
            ):
                raise ValueError("assembly failure stops recognition")
            self._require_failure_code()
            return
        if self.assembly_status is not LayoutEquationCanaryStageStatus.COMPLETE:
            raise ValueError(
                "completed projection requires assembly evaluation"
            )
        self._require_count("assembly_count", self.assembly_count)
        if self.assembly_count != self.projection_candidate_count:
            raise ValueError(
                "assembly count must equal projection candidate count"
            )
        if self.recognition_status is LayoutEquationCanaryStageStatus.FAILED:
            self._require_failed_stage_counts(
                stage="recognition",
                counts=(
                    self.recognition_proposal_count,
                    self.recognition_proposed_count,
                    self.recognition_failed_count,
                    self.recognition_not_requested_count,
                ),
            )
            self._require_failure_code()
            return
        if self.recognition_status is not (
            LayoutEquationCanaryStageStatus.COMPLETE
        ):
            raise ValueError(
                "completed assembly requires recognition evaluation"
            )
        self._require_count(
            "recognition_proposal_count", self.recognition_proposal_count
        )
        if self.recognition_proposal_count != self.assembly_count:
            raise ValueError(
                "recognition proposal count must equal assembly count"
            )
        for name, value in (
            ("recognition_proposed_count", self.recognition_proposed_count),
            ("recognition_failed_count", self.recognition_failed_count),
            (
                "recognition_not_requested_count",
                self.recognition_not_requested_count,
            ),
        ):
            self._require_count(name, value)
        proposed_count = self.recognition_proposed_count
        failed_count = self.recognition_failed_count
        not_requested_count = self.recognition_not_requested_count
        if (
            proposed_count is None
            or failed_count is None
            or not_requested_count is None
        ):
            raise AssertionError("validated recognition count is absent")
        if (
            proposed_count + failed_count + not_requested_count
            != self.recognition_proposal_count
        ):
            raise ValueError(
                "recognition disposition counts must cover every proposal"
            )
        if self.failure_code is not None:
            raise ValueError("completed page cannot carry a failure code")

    def _require_downstream_not_evaluated(self, reason: str) -> None:
        if (
            self.assembly_status
            is not LayoutEquationCanaryStageStatus.NOT_EVALUATED
            or self.recognition_status
            is not LayoutEquationCanaryStageStatus.NOT_EVALUATED
            or self.assembly_count is not None
            or any(
                value is not None
                for value in (
                    self.recognition_proposal_count,
                    self.recognition_proposed_count,
                    self.recognition_failed_count,
                    self.recognition_not_requested_count,
                )
            )
        ):
            raise ValueError(f"{reason} stops downstream evaluation")

    @staticmethod
    def _require_failed_stage_counts(
        *, stage: str, counts: tuple[int | None, ...]
    ) -> None:
        if any(value is not None for value in counts):
            raise ValueError(f"failed {stage} cannot report completed counts")

    @staticmethod
    def _require_count(name: str, value: int | None) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    def _require_failure_code(self) -> None:
        if self.failure_code is None:
            raise ValueError("stopped or failed page requires a failure code")


@dataclass(frozen=True, slots=True)
class LayoutEquationCanaryTrustedEvidence:
    """Externally supplied typed evidence for one evaluated bridge page."""

    case_id: str
    source_sha256: str
    page_index: int
    admission_result: CocoLayoutRegionAdmissionResult
    projection: CocoLayoutEquationProjectionResult | None
    assembly: EquationAssemblyResult | None
    recognition: EquationRecognitionArtifact | None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise ValueError("trusted case_id must be non-empty")
        if not SHA256Hash.is_canonical(self.source_sha256):
            raise ValueError("trusted source_sha256 must be canonical")
        if (
            isinstance(self.page_index, bool)
            or not isinstance(self.page_index, int)
            or self.page_index < 0
        ):
            raise ValueError("trusted page_index must be non-negative")
        if type(self.admission_result) is not CocoLayoutRegionAdmissionResult:
            raise TypeError(
                "trusted admission_result must be exact typed evidence"
            )
        formula_admission = require_formula_admission(self.admission_result)
        render = self.admission_result.request.detector_result.request.render
        if render.source_blob_id != f"blob:sha256:{self.source_sha256}":
            raise ValueError("trusted admission source differs from the page")
        if render.page_index != self.page_index:
            raise ValueError("trusted admission page differs from the page")
        if self.projection is None:
            if self.assembly is not None or self.recognition is not None:
                raise ValueError("trusted evidence must be stage ordered")
            return
        if (
            formula_admission.status
            is not CocoLayoutCategoryAdmissionStatus.ADMITTED
        ):
            raise ValueError("non-admitted category cannot have projection")
        if type(self.projection) is not CocoLayoutEquationProjectionResult:
            raise TypeError("trusted projection must be exact typed evidence")
        if self.projection.request.admission_result != self.admission_result:
            raise ValueError("trusted projection differs from its admission")
        if (
            self.projection.request.document.source.content_hash
            != self.source_sha256
        ):
            raise ValueError("trusted projection source differs from the page")
        if self.assembly is None:
            if self.recognition is not None:
                raise ValueError("trusted recognition requires assembly")
            return
        if type(self.assembly) is not EquationAssemblyResult:
            raise TypeError("trusted assembly must be exact typed evidence")
        if self.assembly.detection_result_id != self.projection.result_id:
            raise ValueError("trusted assembly differs from its projection")
        if self.recognition is None:
            return
        if type(self.recognition) is not EquationRecognitionArtifact:
            raise TypeError("trusted recognition must be exact typed evidence")
        if self.recognition.assembly_artifact_id != self.assembly.artifact_id:
            raise ValueError("trusted recognition differs from its assembly")


@dataclass(frozen=True, slots=True)
class LayoutEquationCanarySummary:
    """Aggregate evaluation coverage without converting it into authority."""

    bridge_status: LayoutEquationCanaryBridgeStatus
    page_count: int
    formula_bearing_page_count: int
    bridge_evaluated_formula_page_count: int
    formula_admission_page_count: int
    formula_escalation_page_count: int
    invalid_parsing_page_count: int
    failed_invocation_page_count: int
    failed_bridge_page_count: int
    admitted_formula_count: int
    projected_formula_count: int
    projection_exclusion_count: int
    recognition_proposed_formula_count: int
    recognition_failed_formula_count: int
    recognition_not_requested_formula_count: int


def layout_equation_canary_page_result_from_json(
    value: object,
) -> LayoutEquationCanaryPageResult:
    """Parse one strict JSON-shaped page result through all invariants."""
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise TypeError("canary page result must be a string-keyed mapping")
    if frozenset(value) != _PAGE_RESULT_KEYS:
        raise ValueError("canary page result fields differ from the schema")
    invocation_status = _optional_enum(
        CocoLayoutDetectorInvocationStatus,
        value["invocation_status"],
        optional=False,
    )
    parsing_status = _optional_enum(
        CocoLayoutDetectorOutputParsingStatus,
        value["parsing_status"],
        optional=True,
    )
    formula_admission_status = _optional_enum(
        CocoLayoutCategoryAdmissionStatus,
        value["formula_admission_status"],
        optional=True,
    )
    projection_status = _optional_enum(
        LayoutEquationCanaryStageStatus,
        value["projection_status"],
        optional=False,
    )
    assembly_status = _optional_enum(
        LayoutEquationCanaryStageStatus,
        value["assembly_status"],
        optional=False,
    )
    recognition_status = _optional_enum(
        LayoutEquationCanaryStageStatus,
        value["recognition_status"],
        optional=False,
    )
    assert isinstance(invocation_status, CocoLayoutDetectorInvocationStatus)
    assert parsing_status is None or isinstance(
        parsing_status, CocoLayoutDetectorOutputParsingStatus
    )
    assert formula_admission_status is None or isinstance(
        formula_admission_status, CocoLayoutCategoryAdmissionStatus
    )
    assert isinstance(projection_status, LayoutEquationCanaryStageStatus)
    assert isinstance(assembly_status, LayoutEquationCanaryStageStatus)
    assert isinstance(recognition_status, LayoutEquationCanaryStageStatus)
    return LayoutEquationCanaryPageResult(
        case_id=value["case_id"],
        source_sha256=value["source_sha256"],
        page_index=value["page_index"],
        invocation_status=invocation_status,
        parsing_status=parsing_status,
        formula_admission_status=formula_admission_status,
        accepted_formula_detection_count=value[
            "accepted_formula_detection_count"
        ],
        projection_status=projection_status,
        projection_candidate_count=value["projection_candidate_count"],
        projection_exclusion_count=value["projection_exclusion_count"],
        assembly_status=assembly_status,
        assembly_count=value["assembly_count"],
        recognition_status=recognition_status,
        recognition_proposal_count=value["recognition_proposal_count"],
        recognition_proposed_count=value["recognition_proposed_count"],
        recognition_failed_count=value["recognition_failed_count"],
        recognition_not_requested_count=value[
            "recognition_not_requested_count"
        ],
        failure_code=value["failure_code"],
    )


def _optional_enum(
    enum_type: type[StrEnum], value: object, *, optional: bool
) -> StrEnum | None:
    if value is None:
        if optional:
            return None
        raise ValueError("required canary enum is absent")
    if not isinstance(value, str):
        raise TypeError("canary enum value must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError("canary enum value is unsupported") from error


def summarize_layout_equation_canary_pages(
    pages: tuple[LayoutEquationCanaryPageResult, ...],
) -> LayoutEquationCanarySummary:
    """Summarize exact coverage without treating non-evaluation as success."""
    if type(pages) is not tuple or any(
        type(page) is not LayoutEquationCanaryPageResult for page in pages
    ):
        raise TypeError("pages must contain exact canary page results")
    case_keys = tuple((page.source_sha256, page.page_index) for page in pages)
    if len(case_keys) != len(set(case_keys)):
        raise ValueError("canary pages must identify unique source pages")
    formula_pages = tuple(
        page
        for page in pages
        if page.accepted_formula_detection_count is not None
        and page.accepted_formula_detection_count > 0
    )
    evaluated_formula_pages = tuple(
        page
        for page in formula_pages
        if page.formula_admission_status
        is CocoLayoutCategoryAdmissionStatus.ADMITTED
        and page.projection_status is LayoutEquationCanaryStageStatus.COMPLETE
        and page.assembly_status is LayoutEquationCanaryStageStatus.COMPLETE
        and page.recognition_status is LayoutEquationCanaryStageStatus.COMPLETE
        and page.projection_exclusion_count == 0
        and page.recognition_failed_count == 0
        and page.recognition_not_requested_count == 0
        and page.recognition_proposed_count
        == page.accepted_formula_detection_count
    )
    failed_bridge_pages = tuple(
        page
        for page in formula_pages
        if page.formula_admission_status
        is CocoLayoutCategoryAdmissionStatus.ADMITTED
        and (
            LayoutEquationCanaryStageStatus.FAILED
            in (
                page.projection_status,
                page.assembly_status,
                page.recognition_status,
            )
            or (page.recognition_failed_count or 0) > 0
        )
    )
    if failed_bridge_pages:
        bridge_status = LayoutEquationCanaryBridgeStatus.FAILED
    elif not formula_pages or not any(
        (page.recognition_proposed_count or 0) > 0 for page in formula_pages
    ):
        bridge_status = LayoutEquationCanaryBridgeStatus.NOT_EVALUATED
    elif len(evaluated_formula_pages) == len(formula_pages):
        bridge_status = LayoutEquationCanaryBridgeStatus.EVALUATED
    else:
        bridge_status = LayoutEquationCanaryBridgeStatus.PARTIALLY_EVALUATED
    return LayoutEquationCanarySummary(
        bridge_status=bridge_status,
        page_count=len(pages),
        formula_bearing_page_count=len(formula_pages),
        bridge_evaluated_formula_page_count=len(evaluated_formula_pages),
        formula_admission_page_count=sum(
            page.formula_admission_status
            is CocoLayoutCategoryAdmissionStatus.ADMITTED
            for page in pages
        ),
        formula_escalation_page_count=sum(
            page.formula_admission_status
            is CocoLayoutCategoryAdmissionStatus.ESCALATION_REQUIRED
            for page in pages
        ),
        invalid_parsing_page_count=sum(
            page.parsing_status is CocoLayoutDetectorOutputParsingStatus.INVALID
            for page in pages
        ),
        failed_invocation_page_count=sum(
            page.invocation_status is CocoLayoutDetectorInvocationStatus.FAILED
            for page in pages
        ),
        failed_bridge_page_count=len(failed_bridge_pages),
        admitted_formula_count=sum(
            page.accepted_formula_detection_count or 0 for page in pages
        ),
        projected_formula_count=sum(
            page.projection_candidate_count or 0 for page in pages
        ),
        projection_exclusion_count=sum(
            page.projection_exclusion_count or 0 for page in pages
        ),
        recognition_proposed_formula_count=sum(
            page.recognition_proposed_count or 0 for page in pages
        ),
        recognition_failed_formula_count=sum(
            page.recognition_failed_count or 0 for page in pages
        ),
        recognition_not_requested_formula_count=sum(
            page.recognition_not_requested_count or 0 for page in pages
        ),
    )


def verify_layout_equation_canary_document(
    document: object,
    *,
    trusted_evidence: tuple[LayoutEquationCanaryTrustedEvidence, ...] = (),
) -> LayoutEquationCanarySummary:
    """Verify a bounded canary result without granting semantic authority."""
    if type(trusted_evidence) is not tuple or any(
        type(item) is not LayoutEquationCanaryTrustedEvidence
        for item in trusted_evidence
    ):
        raise TypeError("trusted_evidence must contain exact typed evidence")
    trusted_by_case = {item.case_id: item for item in trusted_evidence}
    if len(trusted_by_case) != len(trusted_evidence):
        raise ValueError("trusted canary case IDs must be unique")
    if not isinstance(document, Mapping) or any(
        not isinstance(key, str) for key in document
    ):
        raise TypeError("canary document must be a string-keyed mapping")
    if frozenset(document) != _CANARY_DOCUMENT_KEYS:
        raise ValueError("canary document fields differ from the schema")
    if document["schema_version"] != "private-layout-equation-canary-v4":
        raise ValueError("canary schema version is unsupported")
    if document["authority"] != (
        "non-authoritative private capability evidence"
    ):
        raise ValueError("canary authority statement differs")
    for name in (
        "model_resource_id",
        "preprocessing_id",
        "preprocessing_original_size_order",
        "recognition_processor_identity",
    ):
        value = document[name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be non-empty")
    raw_pages = document["page_results"]
    if not isinstance(raw_pages, list) or not 1 <= len(raw_pages) <= 128:
        raise ValueError("canary page result count is out of bounds")
    pages = tuple(
        layout_equation_canary_page_result_from_json(value)
        for value in raw_pages
    )
    expected_summary = summarize_layout_equation_canary_pages(pages)
    if document["summary"] != _summary_json(expected_summary):
        raise ValueError("canary summary differs from page evidence")
    raw_records = document["evidence_records"]
    if not isinstance(raw_records, list) or len(raw_records) != len(pages):
        raise ValueError("canary evidence record coverage differs")
    used_trusted_cases: set[str] = set()
    for page, record in zip(pages, raw_records, strict=True):
        trusted = trusted_by_case.get(page.case_id)
        if page.formula_admission_status in (
            CocoLayoutCategoryAdmissionStatus.ADMITTED,
            CocoLayoutCategoryAdmissionStatus.EMPTY,
        ):
            if trusted is None:
                raise ValueError(
                    "evaluated admission requires independently trusted "
                    "evidence"
                )
            used_trusted_cases.add(page.case_id)
        _verify_evidence_record(page=page, value=record, trusted=trusted)
    if used_trusted_cases != set(trusted_by_case):
        raise ValueError("trusted evidence contains unused canary cases")
    _verify_top_level_evidence_identities(
        document=document,
        trusted_evidence=trusted_evidence,
    )
    return expected_summary


def _verify_top_level_evidence_identities(
    *,
    document: Mapping[object, object],
    trusted_evidence: tuple[LayoutEquationCanaryTrustedEvidence, ...],
) -> None:
    for trusted in trusted_evidence:
        parsing_result = trusted.admission_result.request.parsing_result
        invocation_request = parsing_result.request.invocation.request
        expected = {
            "model_resource_id": (
                invocation_request.configuration.resource.resource_id
            ),
            "preprocessing_id": (
                invocation_request.preprocessing.preprocessing_id
            ),
            "preprocessing_original_size_order": (
                invocation_request.preprocessing.original_size_order.value
            ),
        }
        for name, expected_value in expected.items():
            if document[name] != expected_value:
                raise ValueError(
                    f"{name} differs from independently trusted evidence"
                )
        if (
            trusted.recognition is not None
            and document["recognition_processor_identity"]
            != trusted.recognition.processor_identity.identity_digest
        ):
            raise ValueError(
                "recognition_processor_identity differs from independently "
                "trusted evidence"
            )


def _summary_json(summary: LayoutEquationCanarySummary) -> dict[str, object]:
    return {
        "bridge_status": summary.bridge_status.value,
        "page_count": summary.page_count,
        "formula_bearing_page_count": summary.formula_bearing_page_count,
        "bridge_evaluated_formula_page_count": (
            summary.bridge_evaluated_formula_page_count
        ),
        "formula_admission_page_count": (summary.formula_admission_page_count),
        "formula_escalation_page_count": (
            summary.formula_escalation_page_count
        ),
        "invalid_parsing_page_count": summary.invalid_parsing_page_count,
        "failed_invocation_page_count": summary.failed_invocation_page_count,
        "failed_bridge_page_count": summary.failed_bridge_page_count,
        "admitted_formula_count": summary.admitted_formula_count,
        "projected_formula_count": summary.projected_formula_count,
        "projection_exclusion_count": summary.projection_exclusion_count,
        "recognition_proposed_formula_count": (
            summary.recognition_proposed_formula_count
        ),
        "recognition_failed_formula_count": (
            summary.recognition_failed_formula_count
        ),
        "recognition_not_requested_formula_count": (
            summary.recognition_not_requested_formula_count
        ),
    }


def _verify_evidence_record(
    *,
    page: LayoutEquationCanaryPageResult,
    value: object,
    trusted: LayoutEquationCanaryTrustedEvidence | None,
) -> None:
    if not isinstance(value, Mapping):
        raise TypeError("canary evidence record must be a mapping")
    expected = {
        "case_id": page.case_id,
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "invocation_status": page.invocation_status.value,
    }
    if any(
        value.get(name) != expected_value
        for name, expected_value in expected.items()
    ):
        raise ValueError("canary evidence record identity differs")
    parsing_value = (
        None if page.parsing_status is None else page.parsing_status.value
    )
    if value.get("parsing_status") != parsing_value:
        raise ValueError("canary evidence parsing status differs")
    admission_value = (
        None
        if page.formula_admission_status is None
        else page.formula_admission_status.value
    )
    if value.get("formula_admission_status") != admission_value:
        raise ValueError("canary evidence admission status differs")
    admission_result_id = value.get("admission_result_id")
    if page.formula_admission_status is None:
        if "admission_result_id" in value:
            raise ValueError("unadmitted page contains an admission identity")
    elif not isinstance(admission_result_id, str) or not admission_result_id:
        raise ValueError("admitted page lacks an exact admission identity")
    if trusted is not None:
        if (
            trusted.case_id != page.case_id
            or trusted.source_sha256 != page.source_sha256
            or trusted.page_index != page.page_index
        ):
            raise ValueError("trusted evidence differs from the page identity")
        if admission_result_id != trusted.admission_result.result_id:
            raise ValueError(
                "canary admission identity differs from trusted evidence"
            )
        trusted_formula_count = len(
            require_formula_admission(
                trusted.admission_result
            ).admitted_adaptations
        )
        if trusted_formula_count != page.accepted_formula_detection_count:
            raise ValueError(
                "canary formula count differs from trusted evidence"
            )
    if (
        page.accepted_formula_detection_count is not None
        and value.get("formula_detection_count")
        != page.accepted_formula_detection_count
    ):
        raise ValueError("canary formula count differs")
    if page.formula_admission_status is CocoLayoutCategoryAdmissionStatus.EMPTY:
        if any(
            name in value
            for name in (
                "projection_result_id",
                "assembly_artifact_id",
                "recognition_artifact_id",
            )
        ):
            raise ValueError("empty formula admission contains stage identity")
        return
    _verify_stage_identity(
        value=value,
        field="projection_result_id",
        status=page.projection_status,
        trusted_identity=(
            None
            if trusted is None or trusted.projection is None
            else trusted.projection.result_id
        ),
    )
    _verify_stage_identity(
        value=value,
        field="assembly_artifact_id",
        status=page.assembly_status,
        trusted_identity=(
            None
            if trusted is None or trusted.assembly is None
            else trusted.assembly.artifact_id
        ),
    )
    _verify_stage_identity(
        value=value,
        field="recognition_artifact_id",
        status=page.recognition_status,
        trusted_identity=(
            None
            if trusted is None or trusted.recognition is None
            else trusted.recognition.artifact_id
        ),
    )
    if trusted is not None:
        if (
            trusted.projection is not None
            and len(trusted.projection.candidates)
            != page.projection_candidate_count
        ):
            raise ValueError("projection count differs from trusted evidence")
        if (
            trusted.projection is not None
            and len(trusted.projection.exclusions)
            != page.projection_exclusion_count
        ):
            raise ValueError("exclusion count differs from trusted evidence")
        if (
            trusted.assembly is not None
            and len(trusted.assembly.assemblies) != page.assembly_count
        ):
            raise ValueError("assembly count differs from trusted evidence")
        if trusted.recognition is not None:
            proposals = trusted.recognition.proposals
            if len(proposals) != page.recognition_proposal_count:
                raise ValueError(
                    "recognition count differs from trusted evidence"
                )
            expected_status_counts = {
                EquationRecognitionStatus.PROPOSED: (
                    page.recognition_proposed_count
                ),
                EquationRecognitionStatus.FAILED: page.recognition_failed_count,
                EquationRecognitionStatus.NOT_REQUESTED: (
                    page.recognition_not_requested_count
                ),
            }
            for status, expected_count in expected_status_counts.items():
                if (
                    sum(item.status is status for item in proposals)
                    != expected_count
                ):
                    raise ValueError(
                        "recognition disposition count differs from trusted "
                        "evidence"
                    )


def _verify_stage_identity(
    *,
    value: Mapping[object, object],
    field: str,
    status: LayoutEquationCanaryStageStatus,
    trusted_identity: str | None,
) -> None:
    if status is LayoutEquationCanaryStageStatus.COMPLETE:
        claimed = value.get(field)
        if not isinstance(claimed, str) or not claimed:
            raise ValueError(f"completed stage lacks {field}")
        if trusted_identity is None or claimed != trusted_identity:
            raise ValueError(f"{field} differs from trusted evidence")
    elif field in value:
        raise ValueError(f"stopped stage contains {field}")
    elif trusted_identity is not None:
        raise ValueError(f"trusted evidence exceeds stopped stage {field}")
