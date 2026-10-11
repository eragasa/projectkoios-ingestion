"""HTTP-safe immutable result of durable page-projection publication."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.page.projection.identity import (
    fingerprint_page_projection_identity,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.page.projection.publication.codec import (
    PageProjectionPublicationReceiptCodec,
)
from projectkoios.ingestion.page.projection.publication.status import (
    PageProjectionPublicationDisposition,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationResult(DataObjectActionResult):
    """Return one exact committed receipt body plus operation disposition."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    disposition: PageProjectionPublicationDisposition
    idempotency_scope_id: str
    request_id: str
    receipt_id: str
    receipt_sha256: SHA256Hash
    receipt_byte_length: int
    receipt_body_json: str
    committed_publication_id: str
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.disposition, PageProjectionPublicationDisposition
        ):
            raise TypeError("disposition must be a publication disposition")
        identity_fields = (
            "idempotency_scope_id",
            "request_id",
            "receipt_id",
            "committed_publication_id",
        )
        for name in identity_fields:
            PAGE_PROJECTION_LIMITS.require_identity(getattr(self, name), name)
        if not self.idempotency_scope_id.startswith(
            "page-projection-publication-idempotency-scope:sha256:"
        ):
            raise ValueError("idempotency_scope_id has the wrong role")
        if not self.receipt_id.startswith(
            "page-projection-publication-receipt:sha256:"
        ):
            raise ValueError("receipt_id has the wrong role")
        if not self.committed_publication_id.startswith(
            "page-projection-publication:sha256:"
        ):
            raise ValueError("committed_publication_id has the wrong role")
        if type(self.receipt_body_json) is not str:
            raise TypeError("receipt_body_json must be text")
        body = self.receipt_body_json.encode("utf-8", errors="strict")
        if (
            type(self.receipt_byte_length) is not int
            or self.receipt_byte_length != len(body)
            or self.receipt_byte_length <= 0
        ):
            raise ValueError("receipt_byte_length differs from its body")
        digest = SHA256Fingerprinter.fingerprint(content=body)
        if self.receipt_sha256 != digest:
            raise ValueError("receipt_sha256 differs from its body")
        expected_receipt_id = (
            "page-projection-publication-receipt:sha256:" + digest
        )
        if self.receipt_id != expected_receipt_id:
            raise ValueError("receipt_id differs from its body")
        receipt = PageProjectionPublicationReceiptCodec().decode(
            body_json=self.receipt_body_json
        )
        if receipt.publication_id != self.committed_publication_id:
            raise ValueError("receipt publication differs from committed head")
        object.__setattr__(self, "receipt_sha256", digest)
        object.__setattr__(
            self,
            "result_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material={
                    "contract_version": self.CONTRACT_VERSION,
                    "disposition": self.disposition,
                    "idempotency_scope_id": self.idempotency_scope_id,
                    "receipt_id": self.receipt_id,
                    "request_id": self.request_id,
                },
            ),
        )
