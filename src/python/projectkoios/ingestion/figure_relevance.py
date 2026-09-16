from __future__ import annotations

import math
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, StrEnum

from projectkoios.ingestion.figures import (
    FigureCandidate,
    FigureDetectionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata, WarningSeverity

FIGURE_RELEVANCE_CONTRACT_VERSION = "1.0"
FIGURE_RELEVANCE_CONFIGURATION_VERSION = "1"
_MAX_SELECTIONS = 256
_MAX_DETECTION_RESULTS = 256
_MAX_QUESTION_CHARACTERS = 65_536
_MAX_RATIONALE_CHARACTERS = 65_536
_MAX_TOTAL_RATIONALE_CHARACTERS = 5_000_000
_MAX_INPUT_ARTIFACT_BYTES = 100_000_000
_MAX_TOTAL_INPUT_ARTIFACT_BYTES = 100_000_000
_MAX_TOTAL_RENDERED_PIXELS = 25_000_000
_MAX_WARNINGS_PER_SELECTION = 256
_MAX_FAILURES_PER_SELECTION = 64
_MAX_TOTAL_WARNINGS = 4_096
_MAX_TOTAL_FAILURES = 1_024
_MAX_WARNING_MESSAGE_CHARACTERS = 65_536
_MAX_FAILURE_MESSAGE_CHARACTERS = 65_536
_MAX_EVIDENCE_ENTRIES = 256
_MAX_EVIDENCE_CHARACTERS = 1_000_000
_MAX_RESOURCES = 64
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_RESULT_BYTES = 64_000_000


class FigureRelevanceLimitError(ValueError):
    """Raised before a relevance contract exceeds a hard bound."""


class FigureRelevanceLevel(StrEnum):
    """Question-specific proposal, never source fact or acceptance."""

    PROPOSED_NECESSARY = "proposed_necessary"
    PROPOSED_SUPPORTING = "proposed_supporting"
    PROPOSED_NOT_NECESSARY = "proposed_not_necessary"


class FigureRelevanceStatus(StrEnum):
    """Adapter execution outcome, never relevance acceptance."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class FigureRelevanceFailureKind(StrEnum):
    INPUT_REJECTED = "input_rejected"
    STALE_INPUT = "stale_input"
    RESOURCE_LIMIT = "resource_limit"
    PROCESSOR_UNAVAILABLE = "processor_unavailable"
    PROCESSOR_ERROR = "processor_error"
    OUTPUT_INVALID = "output_invalid"
    OUTPUT_INCOMPLETE = "output_incomplete"


class FigureRelevanceResourceIdentityKind(StrEnum):
    SHA256 = "sha256"
    EXPLICIT = "explicit"


@dataclass(frozen=True)
class FigureRelevanceScore:
    """A normalized relevance score with explicit method semantics."""

    value: float
    method: str
    method_version: str
    scale: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _unit_float("relevance score", self.value)
        )
        _identity_fields(self.method, self.method_version, self.scale)

    def identity_parts(self) -> tuple[object, ...]:
        return (self.value, self.method, self.method_version, self.scale)


@dataclass(frozen=True)
class FigureRelevanceConfidence:
    """Optional confidence in the proposal, distinct from relevance score."""

    value: float
    method: str
    method_version: str
    scale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _unit_float("confidence", self.value))
        _identity_fields(self.method, self.method_version, self.scale)

    def identity_parts(self) -> tuple[object, ...]:
        return (self.value, self.method, self.method_version, self.scale)


@dataclass(frozen=True)
class FigureRelevanceResourceIdentity:
    resource_name: str
    identity_kind: FigureRelevanceResourceIdentityKind
    resource_identity: str

    def __post_init__(self) -> None:
        _bounded_string("resource name", self.resource_name, nonempty=True)
        if not isinstance(
            self.identity_kind, FigureRelevanceResourceIdentityKind
        ):
            raise TypeError(
                "unsupported figure-relevance resource identity kind"
            )
        _bounded_string(
            "resource identity", self.resource_identity, nonempty=True
        )
        if self.identity_kind is FigureRelevanceResourceIdentityKind.SHA256:
            _sha256("resource identity", self.resource_identity)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.resource_name,
            self.identity_kind.value,
            self.resource_identity,
        )


@dataclass(frozen=True)
class FigureRelevanceProcessorIdentity:
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str
    resources: tuple[FigureRelevanceResourceIdentity, ...] = ()

    def __post_init__(self) -> None:
        _identity_fields(
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
        )
        _require_tuple("resources", self.resources)
        if len(self.resources) > _MAX_RESOURCES:
            raise FigureRelevanceLimitError("too many resource identities")
        if any(
            not isinstance(item, FigureRelevanceResourceIdentity)
            for item in self.resources
        ):
            raise TypeError("resources contain an unsupported value")
        names = tuple(item.resource_name for item in self.resources)
        if len(set(names)) != len(names):
            raise ValueError("resource names must be unique")
        if names != tuple(sorted(names)):
            raise ValueError("resource identities must be ordered by name")

    @property
    def identity_digest(self) -> str:
        return stable_id("figure-relevance-processor", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.processor_name,
            self.processor_version,
            self.backend_name,
            self.backend_version,
            tuple(item.identity_parts() for item in self.resources),
        )


@dataclass(frozen=True)
class FigureRelevanceConfiguration:
    configuration_version: str = FIGURE_RELEVANCE_CONFIGURATION_VERSION
    necessary_score_threshold: float = 0.80
    supporting_score_threshold: float = 0.40
    max_selections: int = _MAX_SELECTIONS
    max_detection_results: int = _MAX_DETECTION_RESULTS
    max_question_characters: int = _MAX_QUESTION_CHARACTERS
    max_rationale_characters: int = _MAX_RATIONALE_CHARACTERS
    max_total_rationale_characters: int = _MAX_TOTAL_RATIONALE_CHARACTERS
    max_input_artifact_bytes: int = _MAX_INPUT_ARTIFACT_BYTES
    max_total_input_artifact_bytes: int = _MAX_TOTAL_INPUT_ARTIFACT_BYTES
    max_total_rendered_pixels: int = _MAX_TOTAL_RENDERED_PIXELS
    max_warnings_per_selection: int = _MAX_WARNINGS_PER_SELECTION
    max_failures_per_selection: int = _MAX_FAILURES_PER_SELECTION
    max_total_warnings: int = _MAX_TOTAL_WARNINGS
    max_total_failures: int = _MAX_TOTAL_FAILURES
    max_warning_message_characters: int = _MAX_WARNING_MESSAGE_CHARACTERS
    max_failure_message_characters: int = _MAX_FAILURE_MESSAGE_CHARACTERS
    max_evidence_entries: int = _MAX_EVIDENCE_ENTRIES
    max_evidence_characters: int = _MAX_EVIDENCE_CHARACTERS
    max_resources: int = _MAX_RESOURCES
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        if self.configuration_version != FIGURE_RELEVANCE_CONFIGURATION_VERSION:
            raise ValueError(
                "unsupported figure-relevance configuration version"
            )
        necessary = _unit_float(
            "necessary score threshold", self.necessary_score_threshold
        )
        supporting = _unit_float(
            "supporting score threshold", self.supporting_score_threshold
        )
        if supporting >= necessary:
            raise ValueError(
                "supporting score threshold must be below necessary threshold"
            )
        object.__setattr__(self, "necessary_score_threshold", necessary)
        object.__setattr__(self, "supporting_score_threshold", supporting)
        for name, hard_maximum in (
            ("max_selections", _MAX_SELECTIONS),
            ("max_detection_results", _MAX_DETECTION_RESULTS),
            ("max_question_characters", _MAX_QUESTION_CHARACTERS),
            ("max_rationale_characters", _MAX_RATIONALE_CHARACTERS),
            (
                "max_total_rationale_characters",
                _MAX_TOTAL_RATIONALE_CHARACTERS,
            ),
            ("max_input_artifact_bytes", _MAX_INPUT_ARTIFACT_BYTES),
            (
                "max_total_input_artifact_bytes",
                _MAX_TOTAL_INPUT_ARTIFACT_BYTES,
            ),
            ("max_total_rendered_pixels", _MAX_TOTAL_RENDERED_PIXELS),
            ("max_warnings_per_selection", _MAX_WARNINGS_PER_SELECTION),
            ("max_failures_per_selection", _MAX_FAILURES_PER_SELECTION),
            ("max_total_warnings", _MAX_TOTAL_WARNINGS),
            ("max_total_failures", _MAX_TOTAL_FAILURES),
            (
                "max_warning_message_characters",
                _MAX_WARNING_MESSAGE_CHARACTERS,
            ),
            (
                "max_failure_message_characters",
                _MAX_FAILURE_MESSAGE_CHARACTERS,
            ),
            ("max_evidence_entries", _MAX_EVIDENCE_ENTRIES),
            ("max_evidence_characters", _MAX_EVIDENCE_CHARACTERS),
            ("max_resources", _MAX_RESOURCES),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        ):
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_maximum:
                raise FigureRelevanceLimitError(
                    f"{name} exceeds its implementation maximum "
                    f"({hard_maximum})"
                )

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "figure-relevance-configuration", self.identity_parts()
        )

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )

    def level_for(self, score: FigureRelevanceScore) -> FigureRelevanceLevel:
        if score.value >= self.necessary_score_threshold:
            return FigureRelevanceLevel.PROPOSED_NECESSARY
        if score.value >= self.supporting_score_threshold:
            return FigureRelevanceLevel.PROPOSED_SUPPORTING
        return FigureRelevanceLevel.PROPOSED_NOT_NECESSARY


@dataclass(frozen=True)
class FigureRelevanceSelection:
    selection_id: str
    detection_result: FigureDetectionResult
    candidate_id: str
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        detection_result: FigureDetectionResult,
        candidate_id: str,
    ) -> FigureRelevanceSelection:
        candidate = _selected_candidate(detection_result, candidate_id)
        return cls(
            selection_id=stable_id(
                "figure-relevance-selection",
                detection_result.result_id,
                candidate.candidate_id,
            ),
            detection_result=detection_result,
            candidate_id=candidate_id,
        )

    @property
    def candidate(self) -> FigureCandidate:
        return _selected_candidate(self.detection_result, self.candidate_id)

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance selection version")
        if not isinstance(self.detection_result, FigureDetectionResult):
            raise TypeError("selection requires a figure detection result")
        candidate = _selected_candidate(
            self.detection_result, self.candidate_id
        )
        expected = stable_id(
            "figure-relevance-selection",
            self.detection_result.result_id,
            candidate.candidate_id,
        )
        if self.selection_id != expected:
            raise ValueError("figure-relevance selection ID is inconsistent")


@dataclass(frozen=True)
class FigureRelevanceRequest:
    request_id: str
    review_question: str
    selections: tuple[FigureRelevanceSelection, ...]
    configuration: FigureRelevanceConfiguration
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        review_question: str,
        selections: tuple[FigureRelevanceSelection, ...],
        configuration: FigureRelevanceConfiguration | None = None,
    ) -> FigureRelevanceRequest:
        actual = configuration or FigureRelevanceConfiguration()
        _validate_request_parts(review_question, selections, actual)
        return cls(
            request_id=_request_id(review_question, selections, actual),
            review_question=review_question,
            selections=selections,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance request version")
        _validate_request_parts(
            self.review_question, self.selections, self.configuration
        )
        if self.request_id != _request_id(
            self.review_question, self.selections, self.configuration
        ):
            raise ValueError("figure-relevance request ID is inconsistent")


@dataclass(frozen=True)
class FigureRelevanceProposal:
    proposal_id: str
    selection_id: str
    candidate_id: str
    configuration_digest: str
    level: FigureRelevanceLevel
    score: FigureRelevanceScore
    confidence: FigureRelevanceConfidence | None
    rationale: str
    evidence_component_ids: tuple[str, ...]
    evidence_association_ids: tuple[str, ...]
    evidence: Metadata
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: FigureRelevanceSelection,
        configuration: FigureRelevanceConfiguration,
        score: FigureRelevanceScore,
        confidence: FigureRelevanceConfidence | None,
        rationale: str,
        evidence_component_ids: tuple[str, ...] = (),
        evidence_association_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
    ) -> FigureRelevanceProposal:
        if not isinstance(selection, FigureRelevanceSelection):
            raise TypeError("selection must be FigureRelevanceSelection")
        if not isinstance(configuration, FigureRelevanceConfiguration):
            raise TypeError(
                "configuration must be FigureRelevanceConfiguration"
            )
        if not isinstance(score, FigureRelevanceScore):
            raise TypeError("score must be FigureRelevanceScore")
        if confidence is not None and not isinstance(
            confidence, FigureRelevanceConfidence
        ):
            raise TypeError("confidence must be FigureRelevanceConfidence")
        _bounded_string(
            "figure-relevance rationale",
            rationale,
            nonempty=True,
            limit=configuration.max_rationale_characters,
        )
        _unique_strings("evidence component IDs", evidence_component_ids)
        _unique_strings("evidence association IDs", evidence_association_ids)
        _validate_configured_proposal_evidence(
            evidence_component_ids,
            evidence_association_ids,
            evidence,
            configuration,
        )
        candidate = selection.candidate
        if not set(evidence_component_ids).issubset(
            component.component_id for component in candidate.components
        ):
            raise ValueError("proposal references an unknown figure component")
        if not set(evidence_association_ids).issubset(
            association.association_id for association in candidate.associations
        ):
            raise ValueError(
                "proposal references an unknown figure association"
            )
        level = configuration.level_for(score)
        digest = configuration.configuration_digest
        proposal_id = _proposal_id(
            selection.selection_id,
            selection.candidate_id,
            digest,
            level,
            score,
            confidence,
            rationale,
            evidence_component_ids,
            evidence_association_ids,
            evidence,
        )
        return cls(
            proposal_id=proposal_id,
            selection_id=selection.selection_id,
            candidate_id=selection.candidate_id,
            configuration_digest=digest,
            level=level,
            score=score,
            confidence=confidence,
            rationale=rationale,
            evidence_component_ids=evidence_component_ids,
            evidence_association_ids=evidence_association_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance proposal version")
        _identity_fields(
            self.selection_id, self.candidate_id, self.configuration_digest
        )
        if not isinstance(self.level, FigureRelevanceLevel):
            raise TypeError("figure-relevance level is unsupported")
        if not isinstance(self.score, FigureRelevanceScore):
            raise TypeError("figure-relevance score is unsupported")
        if self.confidence is not None and not isinstance(
            self.confidence, FigureRelevanceConfidence
        ):
            raise TypeError("figure-relevance confidence is unsupported")
        _bounded_string(
            "figure-relevance rationale",
            self.rationale,
            nonempty=True,
            limit=_MAX_RATIONALE_CHARACTERS,
        )
        if not self.rationale.strip():
            raise ValueError("figure-relevance rationale must contain text")
        _unique_strings("evidence component IDs", self.evidence_component_ids)
        _unique_strings(
            "evidence association IDs", self.evidence_association_ids
        )
        _validate_metadata(self.evidence)
        _validate_proposal_evidence_limits(
            self.evidence_component_ids,
            self.evidence_association_ids,
            self.evidence,
            _MAX_EVIDENCE_ENTRIES,
            _MAX_EVIDENCE_CHARACTERS,
        )
        expected = _proposal_id(
            self.selection_id,
            self.candidate_id,
            self.configuration_digest,
            self.level,
            self.score,
            self.confidence,
            self.rationale,
            self.evidence_component_ids,
            self.evidence_association_ids,
            self.evidence,
        )
        if self.proposal_id != expected:
            raise ValueError("figure-relevance proposal ID is inconsistent")


@dataclass(frozen=True)
class FigureRelevanceWarning:
    warning_id: str
    selection_id: str
    code: str
    severity: WarningSeverity
    message: str
    evidence: Metadata = ()
    suggested_recovery: str | None = None
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        code: str,
        severity: WarningSeverity,
        message: str,
        evidence: Metadata = (),
        suggested_recovery: str | None = None,
    ) -> FigureRelevanceWarning:
        warning_id = stable_id(
            "figure-relevance-warning",
            selection_id,
            code,
            severity.value,
            message,
            evidence,
            suggested_recovery,
        )
        return cls(
            warning_id=warning_id,
            selection_id=selection_id,
            code=code,
            severity=severity,
            message=message,
            evidence=evidence,
            suggested_recovery=suggested_recovery,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance warning version")
        _identity_fields(self.selection_id, self.code)
        if not isinstance(self.severity, WarningSeverity):
            raise TypeError("figure-relevance warning severity is unsupported")
        _bounded_string(
            "warning message",
            self.message,
            nonempty=True,
            limit=_MAX_WARNING_MESSAGE_CHARACTERS,
        )
        _validate_metadata(self.evidence)
        if self.suggested_recovery is not None:
            _bounded_string(
                "suggested recovery",
                self.suggested_recovery,
                nonempty=True,
                limit=_MAX_WARNING_MESSAGE_CHARACTERS,
            )
        expected = stable_id(
            "figure-relevance-warning",
            self.selection_id,
            self.code,
            self.severity.value,
            self.message,
            self.evidence,
            self.suggested_recovery,
        )
        if self.warning_id != expected:
            raise ValueError("figure-relevance warning ID is inconsistent")


@dataclass(frozen=True)
class FigureRelevanceFailure:
    failure_id: str
    selection_id: str
    kind: FigureRelevanceFailureKind
    message: str
    retryable: bool
    evidence: Metadata = ()
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection_id: str,
        kind: FigureRelevanceFailureKind,
        message: str,
        retryable: bool,
        evidence: Metadata = (),
    ) -> FigureRelevanceFailure:
        failure_id = stable_id(
            "figure-relevance-failure",
            selection_id,
            kind.value,
            message,
            retryable,
            evidence,
        )
        return cls(
            failure_id=failure_id,
            selection_id=selection_id,
            kind=kind,
            message=message,
            retryable=retryable,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance failure version")
        _identity_fields(self.selection_id)
        if not isinstance(self.kind, FigureRelevanceFailureKind):
            raise TypeError("figure-relevance failure kind is unsupported")
        _bounded_string(
            "failure message",
            self.message,
            nonempty=True,
            limit=_MAX_FAILURE_MESSAGE_CHARACTERS,
        )
        if not isinstance(self.retryable, bool):
            raise TypeError("failure retryable must be a boolean")
        _validate_metadata(self.evidence)
        expected = stable_id(
            "figure-relevance-failure",
            self.selection_id,
            self.kind.value,
            self.message,
            self.retryable,
            self.evidence,
        )
        if self.failure_id != expected:
            raise ValueError("figure-relevance failure ID is inconsistent")


@dataclass(frozen=True)
class FigureRelevanceSelectionResult:
    selection_result_id: str
    selection_id: str
    candidate_id: str
    status: FigureRelevanceStatus
    proposal: FigureRelevanceProposal | None
    warnings: tuple[FigureRelevanceWarning, ...]
    failures: tuple[FigureRelevanceFailure, ...]
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        selection: FigureRelevanceSelection,
        status: FigureRelevanceStatus,
        proposal: FigureRelevanceProposal | None,
        warnings: tuple[FigureRelevanceWarning, ...] = (),
        failures: tuple[FigureRelevanceFailure, ...] = (),
    ) -> FigureRelevanceSelectionResult:
        selection_result_id = _selection_result_id(
            selection.selection_id,
            selection.candidate_id,
            status,
            proposal,
            warnings,
            failures,
        )
        return cls(
            selection_result_id=selection_result_id,
            selection_id=selection.selection_id,
            candidate_id=selection.candidate_id,
            status=status,
            proposal=proposal,
            warnings=warnings,
            failures=failures,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError(
                "unsupported figure-relevance selection-result version"
            )
        _identity_fields(self.selection_id, self.candidate_id)
        if not isinstance(self.status, FigureRelevanceStatus):
            raise TypeError("figure-relevance status is unsupported")
        if self.proposal is not None and not isinstance(
            self.proposal, FigureRelevanceProposal
        ):
            raise TypeError("figure-relevance proposal is unsupported")
        _require_tuple("selection warnings", self.warnings)
        _require_tuple("selection failures", self.failures)
        if any(
            not isinstance(item, FigureRelevanceWarning)
            for item in self.warnings
        ) or any(
            not isinstance(item, FigureRelevanceFailure)
            for item in self.failures
        ):
            raise TypeError("selection result contains an unsupported value")
        if len(self.warnings) > _MAX_WARNINGS_PER_SELECTION:
            raise FigureRelevanceLimitError("too many selection warnings")
        if len(self.failures) > _MAX_FAILURES_PER_SELECTION:
            raise FigureRelevanceLimitError("too many selection failures")
        if any(
            item.selection_id != self.selection_id for item in self.warnings
        ):
            raise ValueError("warning selection identity is inconsistent")
        if any(
            item.selection_id != self.selection_id for item in self.failures
        ):
            raise ValueError("failure selection identity is inconsistent")
        if self.proposal is not None and (
            self.proposal.selection_id != self.selection_id
            or self.proposal.candidate_id != self.candidate_id
        ):
            raise ValueError("proposal selection identity is inconsistent")
        if (
            self.proposal is not None
            and self.proposal.confidence is None
            and not self.warnings
        ):
            raise ValueError(
                "unavailable proposal confidence requires a warning"
            )
        if self.status is FigureRelevanceStatus.COMPLETED:
            if self.proposal is None or self.failures:
                raise ValueError(
                    "completed relevance requires one proposal and no failures"
                )
        elif self.status is FigureRelevanceStatus.PARTIAL:
            if self.proposal is None or not self.failures:
                raise ValueError(
                    "partial relevance requires a proposal and failure"
                )
        elif self.proposal is not None or not self.failures:
            raise ValueError(
                "failed relevance requires failure without proposal"
            )
        warning_ids = tuple(item.warning_id for item in self.warnings)
        failure_ids = tuple(item.failure_id for item in self.failures)
        if len(set(warning_ids)) != len(warning_ids):
            raise ValueError("selection warning IDs must be unique")
        if len(set(failure_ids)) != len(failure_ids):
            raise ValueError("selection failure IDs must be unique")
        expected = _selection_result_id(
            self.selection_id,
            self.candidate_id,
            self.status,
            self.proposal,
            self.warnings,
            self.failures,
        )
        if self.selection_result_id != expected:
            raise ValueError(
                "figure-relevance selection-result ID is inconsistent"
            )


@dataclass(frozen=True)
class FigureRelevanceResult:
    result_id: str
    request: FigureRelevanceRequest
    processor_identity: FigureRelevanceProcessorIdentity
    selection_results: tuple[FigureRelevanceSelectionResult, ...]
    cache_key: str
    contract_version: str = FIGURE_RELEVANCE_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: FigureRelevanceRequest,
        processor_identity: FigureRelevanceProcessorIdentity,
        selection_results: tuple[FigureRelevanceSelectionResult, ...],
    ) -> FigureRelevanceResult:
        cache_key = build_figure_relevance_cache_key(
            request, processor_identity
        )
        result_id = _result_id(
            request.request_id,
            processor_identity,
            selection_results,
            cache_key,
        )
        return cls(
            result_id=result_id,
            request=request,
            processor_identity=processor_identity,
            selection_results=selection_results,
            cache_key=cache_key,
        )

    def __post_init__(self) -> None:
        if self.contract_version != FIGURE_RELEVANCE_CONTRACT_VERSION:
            raise ValueError("unsupported figure-relevance result version")
        _validate_result(self)
        expected = _result_id(
            self.request.request_id,
            self.processor_identity,
            self.selection_results,
            self.cache_key,
        )
        if self.result_id != expected:
            raise ValueError("figure-relevance result ID is inconsistent")


def build_figure_relevance_cache_key(
    request: FigureRelevanceRequest,
    processor_identity: FigureRelevanceProcessorIdentity,
) -> str:
    if not isinstance(request, FigureRelevanceRequest):
        raise TypeError("request must be FigureRelevanceRequest")
    if not isinstance(processor_identity, FigureRelevanceProcessorIdentity):
        raise TypeError(
            "processor_identity must be FigureRelevanceProcessorIdentity"
        )
    if len(processor_identity.resources) > request.configuration.max_resources:
        raise FigureRelevanceLimitError("resources exceed max_resources")
    return stable_id(
        "figure-relevance-cache",
        FIGURE_RELEVANCE_CONTRACT_VERSION,
        FIGURE_RELEVANCE_CONFIGURATION_VERSION,
        request.request_id,
        processor_identity.identity_parts(),
    )


def _validate_request_parts(
    review_question: str,
    selections: tuple[FigureRelevanceSelection, ...],
    configuration: FigureRelevanceConfiguration,
) -> None:
    if not isinstance(configuration, FigureRelevanceConfiguration):
        raise TypeError("configuration must be FigureRelevanceConfiguration")
    _bounded_string(
        "review question",
        review_question,
        nonempty=True,
        limit=configuration.max_question_characters,
    )
    if not review_question.strip():
        raise ValueError("review question must contain text")
    _require_tuple("selections", selections)
    if not selections:
        raise ValueError("figure-relevance request requires a selection")
    if len(selections) > configuration.max_selections:
        raise FigureRelevanceLimitError("selections exceed max_selections")
    if any(
        not isinstance(item, FigureRelevanceSelection) for item in selections
    ):
        raise TypeError("selections contain an unsupported value")
    selection_ids = tuple(item.selection_id for item in selections)
    if len(set(selection_ids)) != len(selection_ids):
        raise ValueError("figure-relevance selections must be unique")
    detection_results = {
        item.detection_result.result_id: item.detection_result
        for item in selections
    }
    if len(detection_results) > configuration.max_detection_results:
        raise FigureRelevanceLimitError(
            "detection results exceed max_detection_results"
        )
    artifact_bytes = 0
    rendered_pixels = 0
    for detection_result in detection_results.values():
        result_bytes = sum(
            artifact.byte_length + (artifact.mask_byte_length or 0)
            for page in detection_result.detection_input.page_evidence
            for artifact in page.embedded_artifacts
        ) + sum(
            component.rendered_region.byte_length
            for candidate in detection_result.candidates
            for component in candidate.components
            if component.rendered_region is not None
        )
        if result_bytes > configuration.max_input_artifact_bytes:
            raise FigureRelevanceLimitError(
                "input artifacts exceed max_input_artifact_bytes"
            )
        artifact_bytes += result_bytes
        rendered_pixels += sum(
            component.rendered_region.width_pixels
            * component.rendered_region.height_pixels
            for candidate in detection_result.candidates
            for component in candidate.components
            if component.rendered_region is not None
        )
    if artifact_bytes > configuration.max_total_input_artifact_bytes:
        raise FigureRelevanceLimitError(
            "input artifacts exceed max_total_input_artifact_bytes"
        )
    if rendered_pixels > configuration.max_total_rendered_pixels:
        raise FigureRelevanceLimitError(
            "rendered pixels exceed max_total_rendered_pixels"
        )
    _validate_retained_size(
        (review_question, selections, configuration),
        configuration.max_result_bytes,
    )


def _validate_result(result: FigureRelevanceResult) -> None:
    if not isinstance(result.request, FigureRelevanceRequest):
        raise TypeError("result request is unsupported")
    if not isinstance(
        result.processor_identity, FigureRelevanceProcessorIdentity
    ):
        raise TypeError("result processor identity is unsupported")
    configuration = result.request.configuration
    if len(result.processor_identity.resources) > configuration.max_resources:
        raise FigureRelevanceLimitError("resources exceed max_resources")
    expected_cache_key = build_figure_relevance_cache_key(
        result.request, result.processor_identity
    )
    if result.cache_key != expected_cache_key:
        raise ValueError("figure-relevance cache key is inconsistent")
    _require_tuple("selection results", result.selection_results)
    if any(
        not isinstance(item, FigureRelevanceSelectionResult)
        for item in result.selection_results
    ):
        raise TypeError("selection results contain an unsupported value")
    if tuple(item.selection_id for item in result.selection_results) != tuple(
        item.selection_id for item in result.request.selections
    ):
        raise ValueError("selection result order or coverage is inconsistent")
    if tuple(item.candidate_id for item in result.selection_results) != tuple(
        item.candidate_id for item in result.request.selections
    ):
        raise ValueError("selection candidate coverage is inconsistent")
    total_warnings = 0
    total_failures = 0
    total_rationale = 0
    selection_by_id = {
        item.selection_id: item for item in result.request.selections
    }
    for item in result.selection_results:
        selection = selection_by_id[item.selection_id]
        if len(item.warnings) > configuration.max_warnings_per_selection:
            raise FigureRelevanceLimitError(
                "selection warnings exceed max_warnings_per_selection"
            )
        if len(item.failures) > configuration.max_failures_per_selection:
            raise FigureRelevanceLimitError(
                "selection failures exceed max_failures_per_selection"
            )
        total_warnings += len(item.warnings)
        total_failures += len(item.failures)
        for warning in item.warnings:
            if (
                len(warning.message)
                > configuration.max_warning_message_characters
            ):
                raise FigureRelevanceLimitError(
                    "warning message exceeds configured limit"
                )
            if (
                warning.suggested_recovery is not None
                and len(warning.suggested_recovery)
                > configuration.max_warning_message_characters
            ):
                raise FigureRelevanceLimitError(
                    "suggested recovery exceeds configured limit"
                )
            _validate_configured_metadata(warning.evidence, configuration)
        for failure in item.failures:
            if (
                len(failure.message)
                > configuration.max_failure_message_characters
            ):
                raise FigureRelevanceLimitError(
                    "failure message exceeds configured limit"
                )
            _validate_configured_metadata(failure.evidence, configuration)
        proposal = item.proposal
        if proposal is None:
            continue
        if proposal.configuration_digest != configuration.configuration_digest:
            raise ValueError("proposal configuration is inconsistent")
        if proposal.level is not configuration.level_for(proposal.score):
            raise ValueError("proposal level is inconsistent with its score")
        if len(proposal.rationale) > configuration.max_rationale_characters:
            raise FigureRelevanceLimitError(
                "proposal rationale exceeds configured limit"
            )
        total_rationale += len(proposal.rationale)
        candidate = selection.candidate
        component_ids = {
            component.component_id for component in candidate.components
        }
        association_ids = {
            association.association_id for association in candidate.associations
        }
        if not set(proposal.evidence_component_ids).issubset(component_ids):
            raise ValueError("proposal references an unknown figure component")
        if not set(proposal.evidence_association_ids).issubset(association_ids):
            raise ValueError(
                "proposal references an unknown figure association"
            )
        _validate_configured_proposal_evidence(
            proposal.evidence_component_ids,
            proposal.evidence_association_ids,
            proposal.evidence,
            configuration,
        )
    if total_warnings > configuration.max_total_warnings:
        raise FigureRelevanceLimitError("warnings exceed max_total_warnings")
    if total_failures > configuration.max_total_failures:
        raise FigureRelevanceLimitError("failures exceed max_total_failures")
    if total_rationale > configuration.max_total_rationale_characters:
        raise FigureRelevanceLimitError(
            "rationales exceed max_total_rationale_characters"
        )
    _validate_retained_size(result, configuration.max_result_bytes)


def _request_id(
    review_question: str,
    selections: tuple[FigureRelevanceSelection, ...],
    configuration: FigureRelevanceConfiguration,
) -> str:
    return stable_id(
        "figure-relevance-request",
        FIGURE_RELEVANCE_CONTRACT_VERSION,
        FIGURE_RELEVANCE_CONFIGURATION_VERSION,
        review_question,
        tuple(
            (
                selection.selection_id,
                selection.detection_result.result_id,
                selection.candidate_id,
            )
            for selection in selections
        ),
        configuration.identity_parts(),
    )


def _proposal_id(
    selection_id: str,
    candidate_id: str,
    configuration_digest: str,
    level: FigureRelevanceLevel,
    score: FigureRelevanceScore,
    confidence: FigureRelevanceConfidence | None,
    rationale: str,
    evidence_component_ids: tuple[str, ...],
    evidence_association_ids: tuple[str, ...],
    evidence: Metadata,
) -> str:
    return stable_id(
        "figure-relevance-proposal",
        selection_id,
        candidate_id,
        configuration_digest,
        level.value,
        score.identity_parts(),
        confidence.identity_parts() if confidence is not None else None,
        rationale,
        evidence_component_ids,
        evidence_association_ids,
        evidence,
    )


def _selection_result_id(
    selection_id: str,
    candidate_id: str,
    status: FigureRelevanceStatus,
    proposal: FigureRelevanceProposal | None,
    warnings: tuple[FigureRelevanceWarning, ...],
    failures: tuple[FigureRelevanceFailure, ...],
) -> str:
    return stable_id(
        "figure-relevance-selection-result",
        selection_id,
        candidate_id,
        status.value,
        proposal.proposal_id if proposal is not None else None,
        tuple(item.warning_id for item in warnings),
        tuple(item.failure_id for item in failures),
    )


def _result_id(
    request_id: str,
    processor_identity: FigureRelevanceProcessorIdentity,
    selection_results: tuple[FigureRelevanceSelectionResult, ...],
    cache_key: str,
) -> str:
    return stable_id(
        "figure-relevance-result",
        request_id,
        processor_identity.identity_parts(),
        tuple(item.selection_result_id for item in selection_results),
        cache_key,
    )


def _selected_candidate(
    detection_result: FigureDetectionResult,
    candidate_id: str,
) -> FigureCandidate:
    _bounded_string("candidate ID", candidate_id, nonempty=True)
    matches = tuple(
        candidate
        for candidate in detection_result.candidates
        if candidate.candidate_id == candidate_id
    )
    if len(matches) != 1:
        raise ValueError(
            "figure-relevance selection must resolve one exact candidate"
        )
    return matches[0]


def _validate_configured_proposal_evidence(
    component_ids: tuple[str, ...],
    association_ids: tuple[str, ...],
    evidence: Metadata,
    configuration: FigureRelevanceConfiguration,
) -> None:
    _validate_configured_metadata(evidence, configuration)
    _validate_proposal_evidence_limits(
        component_ids,
        association_ids,
        evidence,
        configuration.max_evidence_entries,
        configuration.max_evidence_characters,
    )


def _validate_proposal_evidence_limits(
    component_ids: tuple[str, ...],
    association_ids: tuple[str, ...],
    evidence: Metadata,
    max_entries: int,
    max_characters: int,
) -> None:
    if len(component_ids) + len(association_ids) + len(evidence) > max_entries:
        raise FigureRelevanceLimitError(
            "proposal evidence exceeds max_evidence_entries"
        )
    if (
        sum(len(value) for value in component_ids)
        + sum(len(value) for value in association_ids)
        + sum(len(key) + len(value) for key, value in evidence)
        > max_characters
    ):
        raise FigureRelevanceLimitError(
            "proposal evidence exceeds max_evidence_characters"
        )


def _validate_configured_metadata(
    value: Metadata,
    configuration: FigureRelevanceConfiguration,
) -> None:
    _validate_metadata(value)
    if len(value) > configuration.max_evidence_entries:
        raise FigureRelevanceLimitError("evidence exceeds max_evidence_entries")
    if sum(len(key) + len(item) for key, item in value) > (
        configuration.max_evidence_characters
    ):
        raise FigureRelevanceLimitError(
            "evidence exceeds max_evidence_characters"
        )


def _validate_metadata(value: Metadata) -> None:
    _require_tuple("metadata", value)
    if len(value) > _MAX_EVIDENCE_ENTRIES:
        raise FigureRelevanceLimitError("too many metadata entries")
    total = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable pairs")
        key, item = entry
        _bounded_string("metadata key", key, nonempty=True)
        _bounded_string("metadata value", item)
        total += len(key) + len(item)
    if total > _MAX_EVIDENCE_CHARACTERS:
        raise FigureRelevanceLimitError("metadata exceeds its hard limit")


def _identity_fields(*values: str) -> None:
    for value in values:
        _bounded_string("identity field", value, nonempty=True)


def _unique_strings(name: str, values: tuple[str, ...]) -> None:
    _require_tuple(name, values)
    for value in values:
        _bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _bounded_string(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_IDENTITY_CHARACTERS,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > limit:
        raise FigureRelevanceLimitError(f"{name} exceeds its hard limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return 0.0 if result == 0.0 else result


def _unit_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return result


def _sha256(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"{name} must be a SHA-256 digest") from error


def _validate_retained_size(value: object, limit: int) -> None:
    total = 0
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (bool, int, float, Enum)):
            total += 16
        elif isinstance(item, str):
            total += len(item.encode("utf-8")) + 8
        elif isinstance(item, bytes):
            total += len(item)
        elif isinstance(item, tuple):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            total += 8 * len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            for field in fields(item):
                total += len(field.name) + 3
                if field.name in (
                    "content",
                    "mask_content",
                ) and item.__class__.__name__ in (
                    "RenderedRegion",
                    "EmbeddedFigureArtifact",
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError(
                "figure-relevance result contains unsupported evidence"
            )
        if total > limit:
            raise FigureRelevanceLimitError(
                "figure-relevance result exceeds max_result_bytes"
            )
