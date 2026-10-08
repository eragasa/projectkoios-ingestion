"""Current backend-neutral reading-evidence storage schema version."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class ReadingEvidenceStorageSchemaVersion:
    """Identify one ordered backend-neutral persistence schema."""

    namespace: str
    version: int

    CURRENT_NAMESPACE = "projectkoios-reading-evidence-storage"
    CURRENT_VERSION = 1

    def __post_init__(self) -> None:
        if type(self.namespace) is not str or not self.namespace:
            raise ValueError("storage schema namespace must be non-empty")
        if len(self.namespace.encode("utf-8", errors="strict")) > 128:
            raise ValueError("storage schema namespace exceeds its limit")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("storage schema version must be positive")

    @classmethod
    def current(cls) -> ReadingEvidenceStorageSchemaVersion:
        """Return the sole schema accepted by current readers."""
        return cls(
            namespace=cls.CURRENT_NAMESPACE,
            version=cls.CURRENT_VERSION,
        )

    @property
    def schema_id(self) -> str:
        """Return one compact exact schema identity."""
        return f"{self.namespace}:v{self.version}"
