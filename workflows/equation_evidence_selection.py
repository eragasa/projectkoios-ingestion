"""Recognition-independent equation-evidence selection policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

EquationEvidenceDisposition = Literal[
    "selected_primary_equation_evidence",
    "retained_auxiliary_equation_evidence",
    "retained_rejected_equation_evidence",
]


@dataclass(frozen=True, slots=True)
class EquationEvidenceSelection:
    """One immutable selection derived only from detector and assembly evidence."""

    POLICY_VERSION: ClassVar[str] = (
        "recognition-independent-equation-evidence-selection-1"
    )
    _KINDS: ClassVar[frozenset[str]] = frozenset(("display", "inline"))
    _DETECTOR_STATUSES: ClassVar[frozenset[str]] = frozenset(
        ("proposed", "ambiguous")
    )

    disposition: EquationEvidenceDisposition
    ineligibility_reasons: tuple[str, ...]
    review_status: Literal["unreviewed"] = "unreviewed"
    accepted: Literal[False] = False
    review_required: Literal[True] = True
    chunk_text_eligible: Literal[False] = False
    recognized_text_retained: Literal[False] = False

    @classmethod
    def from_assembly_evidence(
        cls,
        *,
        kind: str,
        rejected: bool,
        detector_evidence_statuses: tuple[str, ...],
    ) -> EquationEvidenceSelection:
        """Classify one assembly without recognition or generated text."""

        if type(kind) is not str or kind not in cls._KINDS:
            raise ValueError("equation assembly kind is unsupported")
        if type(rejected) is not bool:
            raise TypeError("equation assembly rejected flag must be boolean")
        if (
            type(detector_evidence_statuses) is not tuple
            or not detector_evidence_statuses
            or any(
                type(status) is not str or status not in cls._DETECTOR_STATUSES
                for status in detector_evidence_statuses
            )
        ):
            raise ValueError("detector evidence statuses are invalid")
        reasons: list[str] = []
        if kind != "display":
            reasons.append("assembly_kind_not_display")
        if rejected:
            reasons.append("assembly_rejected")
        if any(status != "proposed" for status in detector_evidence_statuses):
            reasons.append("detector_evidence_not_proposed")
        if rejected:
            disposition: EquationEvidenceDisposition = (
                "retained_rejected_equation_evidence"
            )
        elif reasons:
            disposition = "retained_auxiliary_equation_evidence"
        else:
            disposition = "selected_primary_equation_evidence"
        return cls(
            disposition=disposition,
            ineligibility_reasons=tuple(reasons),
        )

    def __post_init__(self) -> None:
        if self.disposition not in (
            "selected_primary_equation_evidence",
            "retained_auxiliary_equation_evidence",
            "retained_rejected_equation_evidence",
        ):
            raise ValueError("equation evidence disposition is unsupported")
        if type(self.ineligibility_reasons) is not tuple or len(
            self.ineligibility_reasons
        ) != len(set(self.ineligibility_reasons)):
            raise ValueError("ineligibility reasons must be a unique tuple")
        if self.disposition == "selected_primary_equation_evidence":
            if self.ineligibility_reasons:
                raise ValueError("selected evidence cannot be ineligible")
        elif not self.ineligibility_reasons:
            raise ValueError("retained evidence requires ineligibility reasons")
        if (
            self.review_status != "unreviewed"
            or self.accepted is not False
            or self.review_required is not True
            or self.chunk_text_eligible is not False
            or self.recognized_text_retained is not False
        ):
            raise ValueError("equation evidence review gates are immutable")
