"""Deterministic eligibility policy for equation recognition."""

from projectkoios.ingestion.equations.assembly.kind import EquationAssemblyKind
from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.equations.detection import EquationEvidenceStatus


def primary_equation_recognition_ineligibility_reasons(
    assembly: EquationAssembly,
) -> tuple[str, ...]:
    """Return reasons that an assembly is not primary evidence."""

    reasons: list[str] = []
    if assembly.kind is not EquationAssemblyKind.DISPLAY:
        reasons.append("assembly_kind_not_display")
    if assembly.rejected:
        reasons.append("assembly_rejected")
    if any(
        status is not EquationEvidenceStatus.PROPOSED
        for status in assembly.detector_evidence_statuses
    ):
        reasons.append("detector_evidence_not_proposed")
    return tuple(reasons)


def is_primary_equation_recognition_candidate(
    assembly: EquationAssembly,
) -> bool:
    """Return whether an assembly is primary recognition evidence."""

    return not primary_equation_recognition_ineligibility_reasons(assembly)
