"""One unreviewed equation-recognition proposal."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.equations.latex import EquationLatex
from projectkoios.ingestion.equations.mathml import EquationMathML
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
    latex: EquationLatex | None
    mathml: EquationMathML | None
    mathml_processor_identity: str | None
    mathml_processor_version: str | None
    warning_codes: tuple[str, ...]
    failure_message: str | None
    processor_identity_digest: str
    contract_version: str = EQUATION_RECOGNITION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_RECOGNITION_CONTRACT_VERSION:
            raise ValueError(
                "unsupported equation recognition proposal version"
            )
        if self.status is EquationRecognitionStatus.PROPOSED:
            if type(self.latex) is not EquationLatex:
                raise ValueError(
                    "proposed equation recognition requires typed LaTeX"
                )
            if len(self.latex.equation_source_ids) != 1:
                raise ValueError(
                    "recognized LaTeX requires one equation-image source"
                )
            if self.failure_message is not None:
                raise ValueError(
                    "proposed equation recognition cannot contain failure"
                )
        elif self.latex is not None:
            raise ValueError(
                "non-proposed equation recognition cannot contain LaTeX"
            )
        elif self.status is EquationRecognitionStatus.FAILED:
            if self.failure_message is None or not self.failure_message.strip():
                raise ValueError(
                    "failed equation recognition requires failure evidence"
                )
        elif self.status is EquationRecognitionStatus.NOT_REQUESTED:
            if self.failure_message is not None:
                raise ValueError(
                    "unrequested equation recognition cannot contain failure"
                )
        else:
            raise TypeError("equation recognition status is invalid")
        if len(self.warning_codes) != len(set(self.warning_codes)):
            raise ValueError("recognition warning codes must be unique")
        if self.mathml is not None:
            if type(self.mathml) is not EquationMathML:
                raise TypeError("recognition MathML must be EquationMathML")
            if self.latex is None or self.mathml.equation_source_ids != (
                self.latex.equation_id,
            ):
                raise ValueError(
                    "recognition MathML must derive from its exact LaTeX"
                )
            if (
                self.mathml_processor_identity is None
                or not self.mathml_processor_identity.strip()
                or self.mathml_processor_version is None
                or not self.mathml_processor_version.strip()
            ):
                raise ValueError(
                    "recognition MathML requires exact processor evidence"
                )
        elif (
            self.mathml_processor_identity is not None
            or self.mathml_processor_version is not None
        ):
            raise ValueError(
                "recognition without MathML cannot contain processor evidence"
            )
        latex_content = self.latex.latex if self.latex is not None else None
        mathml_content = self.mathml.mathml if self.mathml is not None else None
        if (
            latex_content is not None
            and len(latex_content) > _MAX_LATEX_CHARACTERS
        ):
            raise ValueError("recognized LaTeX exceeds the limit")
        expected = stable_id(
            "equation-recognition-proposal",
            EQUATION_RECOGNITION_CONTRACT_VERSION,
            self.assembly_id,
            self.status,
            latex_content,
            mathml_content,
            self.warning_codes,
            self.failure_message,
            self.processor_identity_digest,
        )
        if self.proposal_id != expected:
            raise ValueError("equation recognition proposal ID is inconsistent")
