"""Complete immutable evidence for extraction read-model projection."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.projector.source import (
    AbstractProjectionSource,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)


@dataclass(frozen=True, slots=True)
class ExtractionPublicationEvidence(AbstractProjectionSource):
    """Retain one journal record with its exact canonical payload bytes.

    Parameters
    ----------
    evidence_id
        Stable identity binding the journal record and payload digest.
    canonical_sha256
        SHA-256 digest of the canonical evidence framing.
    record
        Validated authoritative publication-journal record.
    payload
        Exact immutable payload bytes named by ``record``.
    contract_version
        Version of this evidence contract.

    Notes
    -----
    Construction performs no disk access. A journal reader must obtain and
    verify the bytes before calling :meth:`create`. Keeping both record and
    bytes makes the projector input complete and prevents mutable lookups.
    """

    CONTRACT_NAME: ClassVar[str] = "extraction-publication-evidence"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    MAXIMUM_PAYLOAD_BYTES: ClassVar[int] = 512_000_000

    evidence_id: str
    canonical_sha256: str
    record: ExtractionPublicationRecord
    payload: bytes
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        record: ExtractionPublicationRecord,
        payload: bytes,
    ) -> ExtractionPublicationEvidence:
        """Create evidence after checking record and payload types.

        Parameters
        ----------
        record
            Exact checksummed journal record.
        payload
            Exact payload bytes referenced by ``record``.

        Returns
        -------
        ExtractionPublicationEvidence
            Immutable complete projection evidence.

        Raises
        ------
        TypeError
            If either value has the wrong concrete type.
        ValueError
            If payload bounds, size, or digest differ from ``record``.
        """
        if type(record) is not ExtractionPublicationRecord:
            raise TypeError("record must be an ExtractionPublicationRecord")
        if type(payload) is not bytes:
            raise TypeError("publication payload must be bytes")
        digest = cls._digest(record=record, payload=payload)
        return cls(
            evidence_id=stable_id(
                "extraction-publication-evidence",
                cls.CONTRACT_VERSION,
                record.record_sha256,
                digest,
            ),
            canonical_sha256=digest,
            record=record,
            payload=payload,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported extraction-publication evidence")
        if type(self.record) is not ExtractionPublicationRecord:
            raise TypeError("publication evidence record is invalid")
        if (
            type(self.payload) is not bytes
            or not self.payload
            or len(self.payload) > self.MAXIMUM_PAYLOAD_BYTES
            or len(self.payload) != self.record.payload_byte_size
            or hashlib.sha256(self.payload).hexdigest()
            != self.record.payload_sha256
        ):
            raise ValueError("publication evidence payload is invalid")
        expected_digest = self._digest(
            record=self.record,
            payload=self.payload,
        )
        if self.canonical_sha256 != expected_digest:
            raise ValueError("publication evidence digest is inconsistent")
        expected_id = stable_id(
            "extraction-publication-evidence",
            self.CONTRACT_VERSION,
            self.record.record_sha256,
            expected_digest,
        )
        if self.evidence_id != expected_id:
            raise ValueError("publication evidence ID is inconsistent")

    @staticmethod
    def _digest(
        *,
        record: ExtractionPublicationRecord,
        payload: bytes,
    ) -> str:
        digest = hashlib.sha256()
        digest.update(record.record_sha256.encode("ascii"))
        # The zero byte makes the framing unambiguous even if a future record
        # digest encoding changes length; it is not part of the source payload.
        digest.update(b"\0")
        digest.update(payload)
        return digest.hexdigest()
