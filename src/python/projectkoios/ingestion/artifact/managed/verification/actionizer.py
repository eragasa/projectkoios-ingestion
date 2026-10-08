"""Effectful exact managed-artifact streaming verification action."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.verification.error import (
    ManagedArtifactVerificationError,
)
from projectkoios.ingestion.artifact.managed.verification.evidence import (
    ManagedArtifactVerificationEvidence,
    ManagedArtifactVerificationEvidenceInventory,
)
from projectkoios.ingestion.artifact.managed.verification.provider import (
    ManagedArtifactByteProvider,
)
from projectkoios.ingestion.artifact.managed.verification.request import (
    ManagedArtifactVerificationRequest,
)
from projectkoios.ingestion.artifact.managed.verification.result import (
    ManagedArtifactVerificationResult,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


class _ObservedChunks(Iterator[bytes]):
    """Validate and measure one transient provider stream as it is consumed."""

    __slots__ = (
        "_chunks",
        "_maximum_bytes",
        "_maximum_chunk_bytes",
        "_prefix",
        "byte_length",
    )

    def __init__(
        self,
        *,
        chunks: Iterable[bytes],
        maximum_bytes: int,
        maximum_chunk_bytes: int,
    ) -> None:
        self._chunks = iter(chunks)
        self._maximum_bytes = maximum_bytes
        self._maximum_chunk_bytes = maximum_chunk_bytes
        self._prefix = bytearray()
        self.byte_length = 0

    @property
    def signature_prefix(self) -> bytes:
        """Return only the bounded prefix retained for media detection."""
        return bytes(self._prefix)

    def __iter__(self) -> _ObservedChunks:
        return self

    def __next__(self) -> bytes:
        chunk = next(self._chunks)
        if type(chunk) is not bytes or not chunk:
            raise ManagedArtifactVerificationError(
                code="provider_chunk_invalid",
                message="managed artifact provider yielded an invalid chunk",
            )
        if len(chunk) > self._maximum_chunk_bytes:
            raise ManagedArtifactVerificationError(
                code="provider_chunk_limit_exceeded",
                message="managed artifact provider exceeded the chunk bound",
            )
        byte_length = self.byte_length + len(chunk)
        if byte_length > self._maximum_bytes:
            raise ManagedArtifactVerificationError(
                code="artifact_byte_limit_exceeded",
                message="managed artifact stream exceeded its exact byte bound",
            )
        remaining_prefix_bytes = (
            MANAGED_ARTIFACT_LIMITS.maximum_media_signature_bytes
            - len(self._prefix)
        )
        if remaining_prefix_bytes > 0:
            self._prefix.extend(chunk[:remaining_prefix_bytes])
        self.byte_length = byte_length
        return chunk


class ManagedArtifactVerificationActionizer(
    DataObjectActionizer[
        ManagedArtifactVerificationRequest,
        ManagedArtifactVerificationResult,
    ]
):
    """Resolve and verify exact artifacts without retaining payload bytes."""

    __slots__ = ("provider",)

    VERIFIER_IMPLEMENTATION_ID = "managed-artifact-verifier:1.0"

    def __init__(self, *, provider: ManagedArtifactByteProvider) -> None:
        if not isinstance(provider, ManagedArtifactByteProvider):
            raise TypeError("provider must be a ManagedArtifactByteProvider")
        MANAGED_ARTIFACT_LIMITS.require_identity_text(
            provider.implementation_id, "provider implementation_id"
        )
        self.provider = provider

    def action(
        self, *, request: ManagedArtifactVerificationRequest
    ) -> ManagedArtifactVerificationResult:
        """Return exact successful coverage or raise one typed failure."""
        if type(request) is not ManagedArtifactVerificationRequest:
            raise TypeError(
                "request must be a ManagedArtifactVerificationRequest"
            )
        if (
            request.provider_implementation_id
            != self.provider.implementation_id
        ):
            raise ManagedArtifactVerificationError(
                code="provider_implementation_differs",
                message=(
                    "configured provider differs from the requested provider"
                ),
            )
        evidence: list[ManagedArtifactVerificationEvidence] = []
        aggregate_bytes = 0
        for reference in request.references:
            with self.provider.open_chunks(
                reference=reference,
                authority_id=request.authority_id,
                maximum_bytes=reference.byte_length,
                chunk_bytes=request.stream_chunk_bytes,
            ) as chunks:
                observed = _ObservedChunks(
                    chunks=chunks,
                    maximum_bytes=reference.byte_length,
                    maximum_chunk_bytes=request.stream_chunk_bytes,
                )
                digest = SHA256Fingerprinter.fingerprint_chunks(chunks=observed)
            if (
                observed.byte_length != reference.byte_length
                or digest != reference.sha256
            ):
                raise ManagedArtifactVerificationError(
                    code="artifact_bytes_differ",
                    message=(
                        "observed artifact bytes differ from their reference"
                    ),
                )
            media_type = _detect_media_type(observed.signature_prefix)
            if media_type is None:
                raise ManagedArtifactVerificationError(
                    code="media_signature_unsupported",
                    message="artifact bytes have no supported media signature",
                )
            if media_type is not reference.media_type:
                raise ManagedArtifactVerificationError(
                    code="media_type_differs",
                    message=(
                        "artifact media signature differs from its reference"
                    ),
                )
            aggregate_bytes += observed.byte_length
            if aggregate_bytes > request.maximum_aggregate_bytes:
                raise ManagedArtifactVerificationError(
                    code="aggregate_byte_limit_exceeded",
                    message=(
                        "observed artifacts exceed the aggregate byte bound"
                    ),
                )
            evidence.append(
                ManagedArtifactVerificationEvidence(
                    reference=reference,
                    observed_sha256=digest,
                    observed_byte_length=observed.byte_length,
                    observed_media_type=media_type,
                    provider_implementation_id=self.provider.implementation_id,
                    verifier_implementation_id=(
                        self.VERIFIER_IMPLEMENTATION_ID
                    ),
                )
            )
        inventory = ManagedArtifactVerificationEvidenceInventory(
            request.references, *evidence
        )
        return ManagedArtifactVerificationResult(
            request=request,
            evidence=inventory,
            verifier_implementation_id=self.VERIFIER_IMPLEMENTATION_ID,
        )


def _detect_media_type(prefix: bytes) -> ManagedArtifactMediaType | None:
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return ManagedArtifactMediaType.IMAGE_PNG
    if prefix.startswith(b"\xff\xd8\xff"):
        return ManagedArtifactMediaType.IMAGE_JPEG
    if (
        len(prefix) >= 12
        and prefix.startswith(b"RIFF")
        and prefix[8:12] == b"WEBP"
    ):
        return ManagedArtifactMediaType.IMAGE_WEBP
    if b"%PDF-" in prefix[:1_024]:
        return ManagedArtifactMediaType.APPLICATION_PDF
    return None
