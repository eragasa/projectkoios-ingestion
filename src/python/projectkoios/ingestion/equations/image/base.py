"""Format-neutral base for exact equation-image representations."""

from __future__ import annotations

import hashlib
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.equations.base import AbstractEquation
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True, slots=True)
class AbstractEquationImage(AbstractEquation):
    """Immutable exact image bytes with format-specific validation."""

    MAX_CONTENT_BYTES: ClassVar[int] = 100_000_000

    source_ids: tuple[str, ...]
    content: bytes
    _equation_id: str = field(init=False, repr=False)
    _content_sha256: str = field(init=False, repr=False)
    _byte_length: int = field(init=False, repr=False)

    @property
    def equation_id(self) -> str:
        return self._equation_id

    @property
    def equation_source_ids(self) -> tuple[str, ...]:
        return self.source_ids

    @property
    @abstractmethod
    def media_type(self) -> str:
        """Return the exact registered media type for this image format."""

    @property
    def content_sha256(self) -> str:
        return self._content_sha256

    @property
    def byte_length(self) -> int:
        return self._byte_length

    @abstractmethod
    def _validate_format(self) -> None:
        """Reject bytes that do not match the concrete image format."""

    def __post_init__(self) -> None:
        self._validate_source_ids(self.source_ids)
        if type(self.content) is not bytes:
            raise TypeError("equation image content must be bytes")
        if not self.content or len(self.content) > self.MAX_CONTENT_BYTES:
            raise ValueError("equation image content size is out of bounds")
        self._validate_format()
        digest = hashlib.sha256(self.content).hexdigest()
        object.__setattr__(self, "_content_sha256", digest)
        object.__setattr__(self, "_byte_length", len(self.content))
        object.__setattr__(
            self,
            "_equation_id",
            stable_id(
                "equation-image",
                self.CONTRACT_VERSION,
                self.media_type,
                digest,
                len(self.content),
                self.source_ids,
            ),
        )
