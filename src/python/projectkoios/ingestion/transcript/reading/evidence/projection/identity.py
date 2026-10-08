"""Hierarchical identity derivation for canonical reading projection."""

from __future__ import annotations

import re
from collections.abc import Iterable

from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
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

_ROLE = re.compile(r"[a-z][a-z0-9_]{0,63}")


class ReadingEvidenceProjectionIdentityDerivation:
    """Derive bounded hierarchical IDs from validated projection inputs."""

    __slots__ = ()

    @classmethod
    def derive_inventory(
        cls,
        *,
        role: str,
        identities: Iterable[str],
    ) -> ReadingEvidenceIdentity:
        """Derive one small identity for an exact ordered identity inventory."""
        if type(role) is not str or _ROLE.fullmatch(role) is None:
            raise ReadingEvidenceError("projection inventory role is invalid")
        values = list(identities)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_total_projection_work:
            raise ReadingEvidenceLimitError(
                "projection inventory identity count exceeds its limit"
            )
        if any(
            type(value) is not str
            or not value
            or len(value) > READING_EVIDENCE_LIMITS.maximum_identity_characters
            for value in values
        ):
            raise ReadingEvidenceError(
                "projection inventory identity is invalid"
            )
        digest = SHA256Fingerprinter.fingerprint(
            content=CanonicalJsonSerializer.serialize_bytes(values)
        )
        return ReadingEvidenceIdentityDerivation.derive(
            kind=ReadingEvidenceIdentityKind.EVIDENCE_INVENTORY,
            prefix="reading-evidence-inventory",
            material={"role": role, "count": len(values), "sha256": digest},
        )

    @classmethod
    def derive_request(
        cls,
        *,
        document_producer_id: ReadingEvidenceIdentity,
        producer_inventory_ids: Iterable[ReadingEvidenceIdentity],
        managed_inventory_id: ReadingEvidenceIdentity,
        expected_inventory_id: ReadingEvidenceIdentity,
        configuration_id: ReadingEvidenceIdentity,
    ) -> ReadingEvidenceIdentity:
        """Derive one projection request identity from bounded aggregate IDs."""
        return ReadingEvidenceIdentityDerivation.derive(
            kind=ReadingEvidenceIdentityKind.PROJECTION_REQUEST,
            prefix="reading-evidence-projection-request",
            material={
                "document_producer_id": document_producer_id.value,
                "producer_inventory_ids": [
                    value.value for value in producer_inventory_ids
                ],
                "managed_inventory_id": managed_inventory_id.value,
                "expected_inventory_id": expected_inventory_id.value,
                "configuration_id": configuration_id.value,
            },
        )

    @classmethod
    def derive_document(
        cls,
        *,
        source_document_id: ReadingEvidenceIdentity,
        page_inventory_id: ReadingEvidenceIdentity,
        lineage_id: ReadingEvidenceIdentity,
        limitation_inventory_id: ReadingEvidenceIdentity,
        contract_version: str,
    ) -> ReadingEvidenceIdentity:
        """Derive one canonical reading document identity."""
        return ReadingEvidenceIdentityDerivation.derive(
            kind=ReadingEvidenceIdentityKind.EVIDENCE_DOCUMENT,
            prefix="reading-evidence-document",
            material={
                "source_document_id": source_document_id.value,
                "page_inventory_id": page_inventory_id.value,
                "lineage_id": lineage_id.value,
                "limitation_inventory_id": limitation_inventory_id.value,
                "contract_version": contract_version,
            },
        )

    @classmethod
    def derive_result(
        cls,
        *,
        request_id: ReadingEvidenceIdentity,
        document_id: ReadingEvidenceIdentity,
        inventory_id: ReadingEvidenceIdentity,
        reconciliation_id: ReadingEvidenceIdentity,
        processor_id: ReadingEvidenceIdentity,
        processor_version: str,
    ) -> ReadingEvidenceIdentity:
        """Derive one complete projection result identity."""
        return ReadingEvidenceIdentityDerivation.derive(
            kind=ReadingEvidenceIdentityKind.PROJECTION_RESULT,
            prefix="reading-evidence-projection-result",
            material={
                "request_id": request_id.value,
                "document_id": document_id.value,
                "inventory_id": inventory_id.value,
                "reconciliation_id": reconciliation_id.value,
                "processor_id": processor_id.value,
                "processor_version": processor_version,
            },
        )
