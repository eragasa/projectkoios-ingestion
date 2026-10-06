"""Processing-state persistence failures."""


class ProcessingStateStoreError(RuntimeError):
    """Raised when a durable processing checkpoint cannot be preserved."""


class ProcessingStateConflictError(ProcessingStateStoreError):
    """Raised when a save does not descend from the current checkpoint."""
