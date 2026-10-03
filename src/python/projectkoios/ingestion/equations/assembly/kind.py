"""Equation assembly kinds."""

from enum import StrEnum


class EquationAssemblyKind(StrEnum):
    """Layout class retained by one assembled equation image."""

    DISPLAY = "display"
    INLINE = "inline"
