"""Managed artifact resource-limit failures."""


class ManagedArtifactLimitError(ValueError):
    """Raised when a managed artifact value exceeds its fixed bounds."""
