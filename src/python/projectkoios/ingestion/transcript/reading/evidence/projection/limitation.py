"""Pure limitation derivation for canonical reading projection."""

from __future__ import annotations

from projectkoios.ingestion.transcript.reading.evidence.equation.status import (  # noqa: E501
    ReadingEquationRecognitionStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.affected import (  # noqa: E501
    ReadingAffectedEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.code import (
    ReadingEvidenceLimitationCode,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.definition import (  # noqa: E501
    ReadingEvidenceLimitation,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.page import (  # noqa: E501
    ReadingEvidencePageProjection,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.request import (  # noqa: E501
    ReadingEvidenceProjectionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)


def derive_reading_evidence_limitations(
    *,
    request: ReadingEvidenceProjectionRequest,
    page_projection: ReadingEvidencePageProjection,
) -> ReadingEvidenceLimitationInventory:
    """Derive exact limitations without repairing or accepting evidence."""
    if type(request) is not ReadingEvidenceProjectionRequest:
        raise TypeError("request must be ReadingEvidenceProjectionRequest")
    if type(page_projection) is not ReadingEvidencePageProjection:
        raise TypeError("page_projection has an unsupported type")
    unreviewed_visual_ids = [
        value.record_id
        for value in request.figures
        if value.assessment.review_status is ReadingReviewStatus.UNREVIEWED
    ]
    unreviewed_visual_ids.extend(
        value.record_id
        for value in request.tables
        if value.assessment.review_status is ReadingReviewStatus.UNREVIEWED
    )
    used_figures = set(page_projection.figure_ids)
    used_tables = set(page_projection.table_ids)
    used_equations = set(page_projection.equation_ids)
    unplaced_ids = [
        value.record_id
        for value in request.figures
        if value.record_id not in used_figures
    ]
    unplaced_ids.extend(
        value.record_id
        for value in request.tables
        if value.record_id not in used_tables
    )
    unplaced_ids.extend(
        value.record_id
        for value in request.equations
        if value.record_id not in used_equations
    )
    geometry_warning_ids = [
        span.geometry_warning_id
        for value in request.clean_text
        for span in value.source_spans
        if span.geometry_warning_id is not None
    ]
    for figure_value in request.figures:
        geometry_warning_ids.extend(
            span.geometry_warning_id
            for span in figure_value.lineage.source_spans
            if span.geometry_warning_id is not None
        )
    for table_value in request.tables:
        geometry_warning_ids.extend(
            span.geometry_warning_id
            for span in table_value.lineage.source_spans
            if span.geometry_warning_id is not None
        )
    for equation_value in request.equations:
        geometry_warning_ids.extend(
            span.geometry_warning_id
            for span in equation_value.lineage.source_spans
            if span.geometry_warning_id is not None
        )
    inputs: tuple[
        tuple[
            ReadingEvidenceLimitationCode,
            tuple[ReadingEvidenceIdentity, ...],
        ],
        ...,
    ] = (
        (
            ReadingEvidenceLimitationCode.UNREVIEWED_VISUAL_EVIDENCE,
            tuple(unreviewed_visual_ids),
        ),
        (
            ReadingEvidenceLimitationCode.UNACCEPTED_EQUATION_EVIDENCE,
            tuple(
                value.record_id
                for value in request.equations
                if not value.gate.accepted
            ),
        ),
        (
            ReadingEvidenceLimitationCode.MISSING_OPTIONAL_RECOGNITION,
            tuple(
                value.record_id
                for value in request.equations
                if value.recognition_status
                is not ReadingEquationRecognitionStatus.SUCCEEDED
            ),
        ),
        (
            ReadingEvidenceLimitationCode.INVALID_GEOMETRY_OMITTED,
            tuple(set(geometry_warning_ids)),
        ),
        (
            ReadingEvidenceLimitationCode.UNPLACED_PRODUCER_EVIDENCE,
            tuple(unplaced_ids),
        ),
    )
    limitations = []
    for code, identities in inputs:
        if identities:
            ordered = tuple(
                sorted(
                    identities,
                    key=lambda value: (value.kind.value, value.value),
                )
            )
            limitations.append(
                ReadingEvidenceLimitation(
                    code=code,
                    affected_ids=ReadingAffectedEvidenceIdentityInventory(
                        *ordered
                    ),
                )
            )
    return ReadingEvidenceLimitationInventory(
        *sorted(limitations, key=lambda value: value.limitation_id.value)
    )
