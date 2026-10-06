"""Deterministic SHA-256 verification."""

from __future__ import annotations

import hmac
from collections.abc import Iterable

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


class SHA256Verifier:
    """Compare exact bytes with an expected canonical SHA-256 hash."""

    __slots__ = ()

    @staticmethod
    def verify(*, content: bytes, expected: SHA256Hash | str) -> bool:
        """Return whether ``content`` has the expected SHA-256 hash."""
        actual = SHA256Fingerprinter.fingerprint(content=content)
        try:
            expected_hash = SHA256Hash(expected)
        except TypeError, ValueError:
            return False
        return hmac.compare_digest(actual, expected_hash)

    @staticmethod
    def verify_chunks(
        *,
        chunks: Iterable[bytes],
        expected: SHA256Hash | str,
    ) -> bool:
        """Return whether ordered ``chunks`` have the expected hash."""
        actual = SHA256Fingerprinter.fingerprint_chunks(chunks=chunks)
        try:
            expected_hash = SHA256Hash(expected)
        except TypeError, ValueError:
            return False
        return hmac.compare_digest(actual, expected_hash)
