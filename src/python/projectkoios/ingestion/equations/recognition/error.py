"""Vendor-neutral equation-recognition failures."""


class EquationRecognitionError(RuntimeError):
    """Raised when a requested recognition transition cannot run."""
