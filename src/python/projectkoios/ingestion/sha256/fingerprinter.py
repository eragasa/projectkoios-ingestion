"""Deterministic SHA-256 fingerprint calculation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from projectkoios.ingestion.sha256.hash import SHA256Hash


class SHA256Fingerprinter:
    """Calculate canonical SHA-256 hashes from exact byte sequences."""

    __slots__ = ()

    @staticmethod
    def fingerprint(*, content: bytes) -> SHA256Hash:
        """Return the SHA-256 hash of one exact byte sequence."""
        if type(content) is not bytes:
            raise TypeError("content must be bytes")
        return SHA256Hash(hashlib.sha256(content).hexdigest())

    @staticmethod
    def fingerprint_chunks(*, chunks: Iterable[bytes]) -> SHA256Hash:
        """Return the SHA-256 hash of exact chunks in supplied order."""
        digest = hashlib.sha256()
        for chunk in chunks:
            if type(chunk) is not bytes:
                raise TypeError("SHA-256 chunks must be bytes")
            digest.update(chunk)
        return SHA256Hash(digest.hexdigest())
