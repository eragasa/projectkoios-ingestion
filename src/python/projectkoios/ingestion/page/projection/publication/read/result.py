"""Transport-safe result of one current-publication read."""

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
from projectkoios.ingestion.page.projection.publication.read.status import (
    PageProjectionPublicationReadDisposition,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


@dataclass(frozen=True, slots=True)
class PageProjectionPublicationReadResult(DataObjectActionResult):
    """Return ABSENT or one exact integrity-verified safe receipt."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-publication-read-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    disposition: PageProjectionPublicationReadDisposition
    source_artifact_id: str
    request_id: str
    current_publication_id: str | None
    receipt_id: str | None
    receipt_sha256: SHA256Hash | None
    receipt_byte_length: int | None
    receipt_body_json: str | None
    result_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.disposition, PageProjectionPublicationReadDisposition
        ):
            raise TypeError(
                "disposition must be a publication read disposition"
            )
        source_artifact_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.source_artifact_id,
            "source_artifact_id",
        )
        if not source_artifact_id.startswith("managed-artifact:sha256:"):
            raise ValueError("source_artifact_id has the wrong role")
        request_id = PAGE_PROJECTION_LIMITS.require_identity(
            self.request_id,
            "request_id",
        )
        if not request_id.startswith(
            "page-projection-publication-read-request:sha256:"
        ):
            raise ValueError("request_id has the wrong role")
        optional_values = (
            self.current_publication_id,
            self.receipt_id,
            self.receipt_sha256,
            self.receipt_byte_length,
            self.receipt_body_json,
        )
        if self.disposition is PageProjectionPublicationReadDisposition.ABSENT:
            if any(value is not None for value in optional_values):
                raise ValueError("absent read cannot contain a current receipt")
        else:
            current_publication_id = self.current_publication_id
            receipt_id = self.receipt_id
            receipt_sha256 = self.receipt_sha256
            receipt_byte_length = self.receipt_byte_length
            receipt_body_json = self.receipt_body_json
            if (
                type(current_publication_id) is not str
                or type(receipt_id) is not str
                or not isinstance(receipt_sha256, SHA256Hash)
                or type(receipt_byte_length) is not int
                or type(receipt_body_json) is not str
            ):
                raise TypeError("current read requires every receipt scalar")
            PAGE_PROJECTION_LIMITS.require_identity(
                current_publication_id,
                "current_publication_id",
            )
            PAGE_PROJECTION_LIMITS.require_identity(receipt_id, "receipt_id")
            if not current_publication_id.startswith(
                "page-projection-publication:sha256:"
            ):
                raise ValueError("current_publication_id has the wrong role")
            body = receipt_body_json.encode("utf-8", errors="strict")
            if receipt_byte_length <= 0 or receipt_byte_length != len(body):
                raise ValueError("receipt_byte_length differs from its body")
            digest = SHA256Fingerprinter.fingerprint(content=body)
            if receipt_sha256 != digest:
                raise ValueError("receipt_sha256 differs from its body")
            expected_receipt_id = (
                "page-projection-publication-receipt:sha256:" + digest
            )
            if receipt_id != expected_receipt_id:
                raise ValueError("receipt_id differs from its body")
            receipt = PageProjectionPublicationReceiptCodec().decode(
                body_json=receipt_body_json
            )
            if receipt.source_artifact_id != source_artifact_id:
                raise ValueError("receipt source differs from its subject")
            if receipt.publication_id != current_publication_id:
                raise ValueError(
                    "receipt publication differs from its current head"
                )
            object.__setattr__(self, "receipt_sha256", digest)
        object.__setattr__(self, "source_artifact_id", source_artifact_id)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(
            self,
            "result_id",
            fingerprint_page_projection_identity(
                namespace=self.CONTRACT_NAME,
                material={
                    "contract_version": self.CONTRACT_VERSION,
                    "disposition": self.disposition,
                    "receipt_id": self.receipt_id,
                    "request_id": request_id,
                    "source_artifact_id": source_artifact_id,
                },
            ),
        )
