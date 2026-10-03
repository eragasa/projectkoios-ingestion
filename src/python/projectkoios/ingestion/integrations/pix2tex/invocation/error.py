"""Pix2Tex subprocess invocation failure."""

from __future__ import annotations

from typing import ClassVar


class Pix2TexInvocationError(RuntimeError):
    """Nonzero whole-invocation failure with bounded diagnostics."""

    MAX_DIAGNOSTIC_BYTES: ClassVar[int] = 4_000_000

    def __init__(self, *, exit_code: int, diagnostic: bytes) -> None:
        super().__init__(f"Pix2Tex invocation exited with code {exit_code}")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise TypeError("Pix2Tex invocation exit code must be an integer")
        if exit_code == 0:
            raise ValueError("Pix2Tex invocation failure requires nonzero exit")
        if type(diagnostic) is not bytes:
            raise TypeError("Pix2Tex invocation diagnostic must be bytes")
        if len(diagnostic) > self.MAX_DIAGNOSTIC_BYTES:
            raise ValueError("Pix2Tex invocation diagnostic exceeds its limit")
        self.exit_code = exit_code
        self.diagnostic = diagnostic
