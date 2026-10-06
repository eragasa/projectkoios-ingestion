"""Canonical SHA-256 hash value."""

from __future__ import annotations

import re
from typing import TypeGuard

_SHA256 = re.compile(r"[0-9a-f]{64}")


class SHA256Hash(str):
    """Represent one canonical lowercase SHA-256 hexadecimal value.

    The value remains a string subtype so existing JSON and persisted contracts
    retain their exact string representation.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> SHA256Hash:
        """Create a hash value after checking its canonical representation."""
        if not cls.is_canonical(value):
            raise ValueError(
                "SHA-256 hash must be 64 lowercase hexadecimal characters"
            )
        return str.__new__(cls, value)

    @classmethod
    def is_canonical(cls, value: object) -> TypeGuard[str]:
        """Return whether ``value`` has the canonical SHA-256 representation."""
        return isinstance(value, str) and _SHA256.fullmatch(value) is not None

    @property
    def value(self) -> str:
        """Return the canonical persisted string representation."""
        return str(self)
