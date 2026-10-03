"""Stable equation-assembly identities."""

from __future__ import annotations

from projectkoios.ingestion.equations.detection import EquationEvidenceStatus
from projectkoios.ingestion.identity import stable_id

EQUATION_ASSEMBLY_CONTRACT_VERSION = "1.0"


def equation_assembly_id(
    detection_result_id: str,
    candidate_ids: tuple[str, ...],
    detector_statuses: tuple[EquationEvidenceStatus, ...],
    rendered_region_id: str,
    sanitized_native_text: str,
    reasons: tuple[str, ...],
    rejected: bool,
) -> str:
    """Return the legacy-stable identity for one exact assembly."""

    return stable_id(
        "equation-assembly",
        EQUATION_ASSEMBLY_CONTRACT_VERSION,
        detection_result_id,
        candidate_ids,
        detector_statuses,
        rendered_region_id,
        sanitized_native_text,
        reasons,
        rejected,
    )
