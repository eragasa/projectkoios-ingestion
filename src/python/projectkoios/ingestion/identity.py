from __future__ import annotations

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


def sha256_digest(content: bytes) -> str:
    return SHA256Fingerprinter.fingerprint(content=content)


def stable_id(namespace: str, *identity_parts: object) -> str:
    if not namespace or ":" in namespace:
        raise ValueError("namespace must be non-empty and cannot contain ':'")

    digest = sha256_digest(
        CanonicalJsonSerializer.serialize_bytes(identity_parts)
    )
    return f"{namespace}:sha256:{digest}"
