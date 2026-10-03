"""One unreviewed equation-recognition proposal."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.recognition.identity import (
    EQUATION_RECOGNITION_CONTRACT_VERSION,
)
from projectkoios.ingestion.equations.recognition.status import (
    EquationRecognitionStatus,
)
from projectkoios.ingestion.identity import stable_id

_MAX_LATEX_CHARACTERS = 16_384


@dataclass(frozen=True)
class EquationRecognitionProposal:
    """Exact automated proposal without acceptance semantics."""

    proposal_id: str
    assembly_id: str
    status: EquationRecognitionStatus
    latex: str | None
    mathml: str | None
    warning_codes: tuple[str, ...]
    failure_message: str | None
    processor_identity_digest: str
    contract_version: str = EQUATION_RECOGNITION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_RECOGNITION_CONTRACT_VERSION:
            raise ValueError(
                "unsupported equation recognition proposal version"
            )
        if self.status is EquationRecognitionStatus.PROPOSED and not self.latex:
            raise ValueError("proposed equation recognition requires LaTeX")
        if (
            self.status is not EquationRecognitionStatus.PROPOSED
            and self.latex is not None
        ):
            raise ValueError(
                "non-proposed equation recognition cannot contain LaTeX"
            )
        if self.latex is not None and len(self.latex) > _MAX_LATEX_CHARACTERS:
            raise ValueError("recognized LaTeX exceeds the limit")
        expected = stable_id(
            "equation-recognition-proposal",
            EQUATION_RECOGNITION_CONTRACT_VERSION,
            self.assembly_id,
            self.status,
            self.latex,
            self.mathml,
            self.warning_codes,
            self.failure_message,
            self.processor_identity_digest,
        )
        if self.proposal_id != expected:
            raise ValueError("equation recognition proposal ID is inconsistent")
