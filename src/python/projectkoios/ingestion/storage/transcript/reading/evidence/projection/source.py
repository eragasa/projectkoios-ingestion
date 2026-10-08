"""Complete source evidence for reading-evidence storage projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.projector.source import (
    AbstractProjectionSource,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.projection.result import (  # noqa: E501
    ReadingEvidenceProjectionResult,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceStorageProjectionSource(AbstractProjectionSource):
    """Bind one complete canonical projection result as source evidence."""

    CONTRACT_NAME: ClassVar[str] = "reading-evidence-storage-projection-source"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    result: ReadingEvidenceProjectionResult
    evidence_id: str = field(init=False)
    canonical_sha256: SHA256Hash = field(init=False)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported storage projection source")
        if type(self.result) is not ReadingEvidenceProjectionResult:
            raise TypeError("result has an unsupported type")
        digest = SHA256Fingerprinter.fingerprint(
            content=self.result.result_id.value.encode("utf-8")
        )
        object.__setattr__(self, "canonical_sha256", digest)
        object.__setattr__(
            self,
            "evidence_id",
            self.result.document.document_id.value,
        )
