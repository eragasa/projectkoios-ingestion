"""Equation-recognition derivation operation names."""

from enum import StrEnum


class EquationRecognitionDerivationOperation(StrEnum):
    """Closed operations emitted by recognition derivation traces."""

    RECOGNITION = "equation-recognition"
    MATHML_CONVERSION = "equation-mathml-conversion"
