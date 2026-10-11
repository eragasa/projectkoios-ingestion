"""Pure owner action for one current page-projection publication."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.page.projection.publication.codec import (
    PageProjectionPublicationReceiptCodec,
)
from projectkoios.ingestion.page.projection.publication.error import (
    PageProjectionPublicationError,
    PageProjectionPublicationFailureReason,
)
from projectkoios.ingestion.page.projection.publication.read.request import (
    PageProjectionPublicationReadRequest,
)
from projectkoios.ingestion.page.projection.publication.read.result import (
    PageProjectionPublicationReadResult,
)
from projectkoios.ingestion.page.projection.publication.read.status import (
    PageProjectionPublicationReadDisposition,
)
from projectkoios.ingestion.page.projection.publication.store import (
    PageProjectionPublicationStore,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash


class PageProjectionPublicationReadActionizer(
    DataObjectActionizer[
        PageProjectionPublicationReadRequest,
        PageProjectionPublicationReadResult,
    ]
):
    """Read one locked current head without mutating publication state."""

    __slots__ = ("store",)

    def __init__(self, *, store: PageProjectionPublicationStore) -> None:
        if not isinstance(store, PageProjectionPublicationStore):
            raise TypeError("store must be a PageProjectionPublicationStore")
        self.store = store

    def action(
        self, *, request: PageProjectionPublicationReadRequest
    ) -> PageProjectionPublicationReadResult:
        """Return ABSENT or one integrity-verified current safe receipt."""
        if type(request) is not PageProjectionPublicationReadRequest:
            raise PageProjectionPublicationError(
                reason=PageProjectionPublicationFailureReason.INVALID_REQUEST,
                message="publication read request has an unsupported type",
            )
        try:
            receipt = self.store.read_current(
                source_artifact_id=request.source_artifact.artifact_id
            )
            if receipt is None:
                return PageProjectionPublicationReadResult(
                    disposition=(
                        PageProjectionPublicationReadDisposition.ABSENT
                    ),
                    source_artifact_id=request.source_artifact.artifact_id,
                    request_id=request.request_id,
                    current_publication_id=None,
                    receipt_id=None,
                    receipt_sha256=None,
                    receipt_byte_length=None,
                    receipt_body_json=None,
                )
            body_json = PageProjectionPublicationReceiptCodec().encode(
                receipt=receipt
            )
            body = body_json.encode("utf-8", errors="strict")
            digest = SHA256Hash(
                SHA256Fingerprinter.fingerprint(content=body)
            )
            return PageProjectionPublicationReadResult(
                disposition=PageProjectionPublicationReadDisposition.CURRENT,
                source_artifact_id=request.source_artifact.artifact_id,
                request_id=request.request_id,
                current_publication_id=receipt.publication_id,
                receipt_id=(
                    "page-projection-publication-receipt:sha256:" + digest
                ),
                receipt_sha256=digest,
                receipt_byte_length=len(body),
                receipt_body_json=body_json,
            )
        except PageProjectionPublicationError:
            raise
        except Exception as error:
            raise PageProjectionPublicationError(
                reason=PageProjectionPublicationFailureReason.UNEXPECTED,
                message="current publication read failed",
            ) from error
