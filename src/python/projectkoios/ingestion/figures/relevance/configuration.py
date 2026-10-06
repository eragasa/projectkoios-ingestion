"""Figure-relevance configuration record."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.figures.relevance.constants import (
    FIGURE_RELEVANCE_CONFIGURATION_VERSION,
)
from projectkoios.ingestion.figures.relevance.level import FigureRelevanceLevel
from projectkoios.ingestion.figures.relevance.limits.definition import (
    _MAX_DETECTION_RESULTS,
    _MAX_EVIDENCE_CHARACTERS,
    _MAX_EVIDENCE_ENTRIES,
    _MAX_FAILURE_MESSAGE_CHARACTERS,
    _MAX_FAILURES_PER_SELECTION,
    _MAX_INPUT_ARTIFACT_BYTES,
    _MAX_QUESTION_CHARACTERS,
    _MAX_RATIONALE_CHARACTERS,
    _MAX_RESOURCES,
    _MAX_RESULT_BYTES,
    _MAX_SELECTIONS,
    _MAX_TOTAL_FAILURES,
    _MAX_TOTAL_INPUT_ARTIFACT_BYTES,
    _MAX_TOTAL_RATIONALE_CHARACTERS,
    _MAX_TOTAL_RENDERED_PIXELS,
    _MAX_TOTAL_WARNINGS,
    _MAX_WARNING_MESSAGE_CHARACTERS,
    _MAX_WARNINGS_PER_SELECTION,
)
from projectkoios.ingestion.figures.relevance.limits.error import (
    FigureRelevanceLimitError,
)
from projectkoios.ingestion.figures.relevance.score import FigureRelevanceScore
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)
from projectkoios.ingestion.identity import stable_id


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
        necessary = value_validation._unit_float(
            "necessary score threshold", self.necessary_score_threshold
        )
        supporting = value_validation._unit_float(
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
            value_validation._positive_integer(name, value)
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
