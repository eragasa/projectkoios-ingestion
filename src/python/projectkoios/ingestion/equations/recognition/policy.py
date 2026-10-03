"""Deterministic eligibility policy for equation recognition."""

from projectkoios.ingestion.equations.assembly.kind import EquationAssemblyKind
from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.equations.detection import EquationEvidenceStatus


def is_primary_equation_recognition_candidate(
    assembly: EquationAssembly,
) -> bool:
    """Return whether an assembly is eligible for primary recognition."""

    return (
        assembly.kind is EquationAssemblyKind.DISPLAY
        and not assembly.rejected
        and all(
            status is EquationEvidenceStatus.PROPOSED
            for status in assembly.detector_evidence_statuses
        )
    )
