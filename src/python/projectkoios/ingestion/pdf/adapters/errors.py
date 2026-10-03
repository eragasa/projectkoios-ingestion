"""Shared typed failures for optional PDF adapter dependencies."""


class PdfDependencyUnavailableError(RuntimeError):
    """Raised when an optional PDF adapter dependency is unavailable."""
