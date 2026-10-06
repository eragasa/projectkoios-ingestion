"""Figure-relevance request validation."""

from __future__ import annotations

from projectkoios.ingestion.figures.relevance.configuration import (
    FigureRelevanceConfiguration,
)
from projectkoios.ingestion.figures.relevance.limits.error import (
    FigureRelevanceLimitError,
)
from projectkoios.ingestion.figures.relevance.selection import (
    FigureRelevanceSelection,
)
from projectkoios.ingestion.figures.relevance.validation import (
    value as value_validation,
)


def _validate_request_parts(
    review_question: str,
    selections: tuple[FigureRelevanceSelection, ...],
    configuration: FigureRelevanceConfiguration,
) -> None:
    if not isinstance(configuration, FigureRelevanceConfiguration):
        raise TypeError("configuration must be FigureRelevanceConfiguration")
    value_validation._bounded_string(
        "review question",
        review_question,
        nonempty=True,
        limit=configuration.max_question_characters,
    )
    if not review_question.strip():
        raise ValueError("review question must contain text")
    value_validation._require_tuple("selections", selections)
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
    value_validation._validate_retained_size(
        (review_question, selections, configuration),
        configuration.max_result_bytes,
    )
