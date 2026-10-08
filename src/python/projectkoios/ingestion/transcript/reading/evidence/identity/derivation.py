"""Bounded deterministic reading evidence identity derivation."""

from __future__ import annotations

import re

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)

_PREFIX = re.compile(r"[a-z][a-z0-9-]{0,63}")


class ReadingEvidenceIdentityDerivation:
    """Derive typed identities from already validated bounded material."""

    __slots__ = ()

    @classmethod
    def derive(
        cls,
        *,
        kind: ReadingEvidenceIdentityKind,
        prefix: str,
        material: object,
    ) -> ReadingEvidenceIdentity:
        """Serialize once and fingerprint the exact identity bytes."""
        if not isinstance(kind, ReadingEvidenceIdentityKind):
            raise TypeError("kind must be ReadingEvidenceIdentityKind")
        if type(prefix) is not str or _PREFIX.fullmatch(prefix) is None:
            raise ReadingEvidenceError("identity prefix is invalid")
        identity_input = CanonicalJsonSerializer.serialize_bytes(material)
        if (
            len(identity_input)
            > READING_EVIDENCE_LIMITS.maximum_identity_input_bytes
        ):
            raise ReadingEvidenceLimitError(
                "reading evidence identity input exceeds its limit"
            )
        digest = SHA256Fingerprinter.fingerprint(content=identity_input)
        return ReadingEvidenceIdentity(
            kind=kind,
            value=f"{prefix}:sha256:{digest}",
        )
