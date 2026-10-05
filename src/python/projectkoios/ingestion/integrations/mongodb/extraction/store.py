"""MongoDB projection of authoritative extraction publications."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from bson import BSON
from bson.errors import InvalidDocument
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.base import (
    AbstractExtractionPublicationStore,
)
from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.reader import (  # noqa: E501
    ExtractionProjectionInventoryReader,
)
from projectkoios.ingestion.storage.extraction.projection_inventory.reader_error import (  # noqa: E501
    ExtractionProjectionInventoryReaderError,
)
from projectkoios.ingestion.storage.extraction.publication.record import (
    ExtractionPublicationRecord,
)
from projectkoios.ingestion.storage.extraction.publication.request import (
    ExtractionPublicationRequest,
)
from projectkoios.ingestion.storage.extraction.publication.result import (
    ExtractionPublicationResult,
)
from projectkoios.ingestion.storage.extraction.recovery.request import (
    ExtractionProjectionRecoveryRequest,
)
from projectkoios.ingestion.storage.extraction.recovery.result import (
    ExtractionProjectionRecoveryResult,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.backend import (  # noqa: E501
    SelectedExtractionProjectionRecoveryBackend,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.backend_error import (  # noqa: E501
    SelectedExtractionProjectionRecoveryBackendError,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.evidence import (  # noqa: E501
    SelectedExtractionProjectionRecoveryEvidence,
)
from projectkoios.ingestion.storage.extraction.selected_recovery.request import (  # noqa: E501
    SelectedExtractionProjectionRecoveryRequest,
)
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

MongoDocument = dict[str, Any]


class MongoExtractionPublicationStore(
    AbstractExtractionPublicationStore,
    ExtractionProjectionInventoryReader,
    SelectedExtractionProjectionRecoveryBackend,
):
    """Idempotent MongoDB read projection backed by a disk journal."""

    DOCUMENTS: ClassVar[str] = "extraction_documents"
    PAGES: ClassVar[str] = "extraction_pages"
    BLOCKS: ClassVar[str] = "extraction_blocks"
    WARNINGS: ClassVar[str] = "extraction_warnings"
    MANIFESTS: ClassVar[str] = "extraction_manifests"
    MAX_DOCUMENT_BYTES: ClassVar[int] = 15_000_000

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        journal: DiskExtractionPublicationStore,
        projection_reference: str | None = None,
    ) -> None:
        if type(journal) is not DiskExtractionPublicationStore:
            raise TypeError("journal must be a DiskExtractionPublicationStore")
        if projection_reference is not None and (
            type(projection_reference) is not str or not projection_reference
        ):
            raise ValueError("projection_reference must be non-empty")
        self.database = database
        self.journal = journal
        self.projection_reference = projection_reference or stable_id(
            "mongodb-extraction-projection",
            "1.0",
            database.name,
        )
        self._indexes_ready = False

    def publish(
        self,
        *,
        request: ExtractionPublicationRequest,
    ) -> ExtractionPublicationResult:
        if type(request) is not ExtractionPublicationRequest:
            raise TypeError("request must be an ExtractionPublicationRequest")
        committed = self.journal.publish(request=request)
        records = self.journal.records()
        record = records[committed.journal_sequence - 1]
        self._project(record)
        return committed

    def recover(
        self,
        *,
        request: ExtractionProjectionRecoveryRequest,
    ) -> ExtractionProjectionRecoveryResult:
        """Rebuild this projection from the authoritative journal."""

        if type(request) is not ExtractionProjectionRecoveryRequest:
            raise TypeError(
                "request must be an ExtractionProjectionRecoveryRequest"
            )
        records = self.journal.records()
        if len(records) > request.maximum_records:
            raise ExtractionPublicationError(
                "recovery journal exceeds the requested record bound"
            )
        for record in records:
            self._project(record)
        return ExtractionProjectionRecoveryResult(
            request_id=request.request_id,
            observed_records=len(records),
            projected_records=len(records),
            last_journal_sequence=records[-1].sequence if records else None,
        )

    def recover_selected(
        self,
        *,
        request: SelectedExtractionProjectionRecoveryRequest,
    ) -> SelectedExtractionProjectionRecoveryEvidence:
        """Recover all and only the exact journal records in the request."""

        if not isinstance(request, SelectedExtractionProjectionRecoveryRequest):
            raise TypeError(
                "request must be a SelectedExtractionProjectionRecoveryRequest"
            )
        if request.projection_reference != self.projection_reference:
            raise SelectedExtractionProjectionRecoveryBackendError(
                code="projection_reference_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message=(
                    "projection reference differs from the configured store"
                ),
            )
        try:
            records = self.journal.records()
        except ExtractionPublicationError as error:
            raise SelectedExtractionProjectionRecoveryBackendError(
                code="authoritative_journal_invalid",
                disposition=(ExtractionActionDisposition.STOP_INVALID_EVIDENCE),
                message="authoritative extraction journal is invalid",
            ) from error
        head = records[-1].record_sha256 if records else None
        if (
            len(records) != request.expected_journal_record_count
            or head != request.expected_journal_head_sha256
        ):
            raise SelectedExtractionProjectionRecoveryBackendError(
                code="authoritative_journal_identity_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="authoritative extraction journal identity differs",
            )
        for selected in request.selected_records:
            if records[selected.sequence - 1] != selected:
                raise SelectedExtractionProjectionRecoveryBackendError(
                    code="selected_publication_record_differs",
                    disposition=(
                        ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                    ),
                    message="selected publication record differs",
                )
        before = self._selected_inventory(request)
        if request.require_empty_projection and any(
            item.document_count for item in before
        ):
            raise SelectedExtractionProjectionRecoveryBackendError(
                code="projection_is_not_empty",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="selected recovery requires an empty projection",
            )
        projected = 0
        try:
            for selected in request.selected_records:
                projected += self._project(selected)
        except ExtractionPublicationError as error:
            cause = error.__cause__
            if isinstance(cause, PyMongoError) and not isinstance(
                cause, DuplicateKeyError
            ):
                code = "projection_write_failed"
                disposition = ExtractionActionDisposition.RETRY_SAME_REQUEST
            elif isinstance(cause, DuplicateKeyError):
                code = "projection_identity_conflict"
                disposition = (
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                )
            else:
                code = "publication_payload_invalid"
                disposition = ExtractionActionDisposition.STOP_INVALID_EVIDENCE
            raise SelectedExtractionProjectionRecoveryBackendError(
                code=code,
                disposition=disposition,
                message="selected extraction projection recovery failed",
            ) from error
        collections = self._selected_inventory(request)
        return SelectedExtractionProjectionRecoveryEvidence.create(
            observed_journal_record_count=len(records),
            observed_journal_head_sha256=head,
            selected_record_count=len(request.selected_records),
            projected_record_count=projected,
            unchanged_record_count=len(request.selected_records) - projected,
            last_selected_sequence=(
                request.selected_records[-1].sequence
                if request.selected_records
                else None
            ),
            collections=collections,
        )

    def _selected_inventory(
        self,
        request: SelectedExtractionProjectionRecoveryRequest,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        try:
            return self.read_inventory(
                projection_reference=request.projection_reference,
                authority_id=request.authority_id,
            )
        except ExtractionProjectionInventoryReaderError as error:
            raise SelectedExtractionProjectionRecoveryBackendError(
                code=error.code,
                disposition=error.disposition,
                message="selected recovery projection inventory failed",
            ) from error

    def read_inventory(
        self,
        *,
        projection_reference: str,
        authority_id: str,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        """Return compact identity/publication digests for owned collections."""

        if projection_reference != self.projection_reference:
            raise ExtractionProjectionInventoryReaderError(
                code="projection_reference_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message=(
                    "projection reference differs from the configured store"
                ),
            )
        if type(authority_id) is not str or not authority_id:
            raise ExtractionProjectionInventoryReaderError(
                code="projection_query_authority_required",
                disposition=ExtractionActionDisposition.AUTHORITY_REQUIRED,
                message="projection query authority is required",
            )
        collections: list[ExtractionProjectionCollectionInventory] = []
        for collection_name in sorted(
            (
                self.DOCUMENTS,
                self.PAGES,
                self.BLOCKS,
                self.WARNINGS,
                self.MANIFESTS,
            )
        ):
            members: list[tuple[str, str]] = []
            try:
                cursor = self.database[collection_name].find(
                    {}, {"_id": 1, "publication_digest": 1}
                )
                for document in cursor:
                    identity = document.get("_id")
                    publication_digest = document.get("publication_digest")
                    if (
                        type(identity) is not str
                        or type(publication_digest) is not str
                    ):
                        raise ExtractionProjectionInventoryReaderError(
                            code="projection_inventory_document_invalid",
                            disposition=(
                                ExtractionActionDisposition.STOP_INVALID_EVIDENCE
                            ),
                            message="projection inventory document is invalid",
                        )
                    members.append((identity, publication_digest))
                    if len(members) > (
                        ExtractionProjectionCollectionInventory.MAXIMUM_DOCUMENTS
                    ):
                        raise ExtractionProjectionInventoryReaderError(
                            code="projection_inventory_limit_exceeded",
                            disposition=(
                                ExtractionActionDisposition.STOP_INVALID_EVIDENCE
                            ),
                            message="projection inventory exceeds its limit",
                        )
            except PyMongoError as error:
                raise ExtractionProjectionInventoryReaderError(
                    code="projection_inventory_query_failed",
                    disposition=(
                        ExtractionActionDisposition.RETRY_SAME_REQUEST
                    ),
                    message="projection inventory query failed",
                ) from error
            try:
                inventory = ExtractionProjectionCollectionInventory.create(
                    collection_name=collection_name,
                    members=tuple(sorted(members)),
                )
            except (TypeError, ValueError) as error:
                raise ExtractionProjectionInventoryReaderError(
                    code="projection_inventory_document_invalid",
                    disposition=(
                        ExtractionActionDisposition.STOP_INVALID_EVIDENCE
                    ),
                    message="projection inventory document is invalid",
                ) from error
            collections.append(inventory)
        return tuple(collections)

    def _project(self, record: ExtractionPublicationRecord) -> int:
        self._ensure_indexes()
        try:
            value = json.loads(self.journal.payload(record))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ExtractionPublicationError(
                "disk recovery payload is not canonical JSON"
            ) from error
        if type(value) is not dict:
            raise ExtractionPublicationError(
                "disk recovery payload root is not an object"
            )
        document = value.get("document")
        manifest = value.get("manifest")
        warnings = value.get("warnings")
        if (
            type(document) is not dict
            or type(manifest) is not dict
            or type(warnings) is not list
        ):
            raise ExtractionPublicationError(
                "disk recovery payload is not an extraction result"
            )
        document_id = document.get("document_id")
        manifest_id = manifest.get("manifest_id")
        pages = document.get("pages")
        if (
            type(document_id) is not str
            or document_id != record.document_id
            or type(manifest_id) is not str
            or manifest_id != record.manifest_id
            or type(pages) is not list
        ):
            raise ExtractionPublicationError(
                "disk recovery payload identities are inconsistent"
            )
        page_ids: list[str] = []
        for page in pages:
            page_id = self._project_page(
                document_id=document_id,
                manifest_id=manifest_id,
                page=page,
                publication_digest=record.payload_sha256,
            )
            page_ids.append(page_id)
        for warning in warnings:
            if (
                type(warning) is not dict
                or type(warning.get("warning_id")) is not str
            ):
                raise ExtractionPublicationError(
                    "extraction warning projection is invalid"
                )
            warning_document = dict(warning)
            warning_document.update(
                {
                    "_id": stable_id(
                        "mongodb-extraction-warning",
                        "1.0",
                        manifest_id,
                        warning["warning_id"],
                    ),
                    "document_id": document_id,
                    "manifest_id": manifest_id,
                    "publication_digest": record.payload_sha256,
                }
            )
            self._replace_create_once(self.WARNINGS, warning_document)
        manifest_document = dict(manifest)
        manifest_document.update(
            {
                "_id": manifest_id,
                "document_id": document_id,
                "publication_digest": record.payload_sha256,
            }
        )
        self._replace_create_once(self.MANIFESTS, manifest_document)
        document_manifest = {
            key: item for key, item in document.items() if key != "pages"
        }
        document_manifest.update(
            {
                "_id": manifest_id,
                "document_id": document_id,
                "manifest_id": manifest_id,
                "page_ids": page_ids,
                "publication_digest": record.payload_sha256,
                "publication_state": "complete",
            }
        )
        created = self._replace_create_once(self.DOCUMENTS, document_manifest)
        return int(created)

    def _project_page(
        self,
        *,
        document_id: str,
        manifest_id: str,
        page: object,
        publication_digest: str,
    ) -> str:
        if type(page) is not dict or type(page.get("page_index")) is not int:
            raise ExtractionPublicationError(
                "extraction page projection is invalid"
            )
        page_index = page["page_index"]
        blocks = page.get("blocks")
        if type(blocks) is not list:
            raise ExtractionPublicationError(
                "extraction page blocks are invalid"
            )
        page_id = stable_id(
            "mongodb-extraction-page",
            "1.0",
            document_id,
            manifest_id,
            page_index,
        )
        block_ids: list[str] = []
        for ordinal, block in enumerate(blocks):
            if (
                type(block) is not dict
                or type(block.get("block_id")) is not str
            ):
                raise ExtractionPublicationError(
                    "extraction block projection is invalid"
                )
            block_document = dict(block)
            block_document.update(
                {
                    "_id": stable_id(
                        "mongodb-extraction-block",
                        "1.0",
                        manifest_id,
                        block["block_id"],
                    ),
                    "document_id": document_id,
                    "manifest_id": manifest_id,
                    "page_id": page_id,
                    "page_index": page_index,
                    "ordinal": ordinal,
                    "publication_digest": publication_digest,
                }
            )
            self._replace_create_once(self.BLOCKS, block_document)
            block_ids.append(block_document["_id"])
        page_document = {
            key: item for key, item in page.items() if key != "blocks"
        }
        page_document.update(
            {
                "_id": page_id,
                "document_id": document_id,
                "manifest_id": manifest_id,
                "block_ids": block_ids,
                "publication_digest": publication_digest,
            }
        )
        self._replace_create_once(self.PAGES, page_document)
        return page_id

    def _replace_create_once(
        self,
        collection_name: str,
        value: MongoDocument,
    ) -> bool:
        digest = value["publication_digest"]
        try:
            encoded = BSON.encode(value)
            if len(encoded) > self.MAX_DOCUMENT_BYTES:
                raise ExtractionPublicationError(
                    "MongoDB extraction projection document is too large"
                )
            result = self.database[collection_name].replace_one(
                {
                    "_id": value["_id"],
                    "publication_digest": digest,
                },
                value,
                upsert=True,
            )
            return result.upserted_id is not None
        except InvalidDocument as error:
            raise ExtractionPublicationError(
                "MongoDB extraction projection document is invalid"
            ) from error
        except DuplicateKeyError as error:
            raise ExtractionPublicationError(
                "MongoDB projection identity has conflicting content"
            ) from error
        except PyMongoError as error:
            raise ExtractionPublicationError(
                "MongoDB extraction projection failed"
            ) from error

    def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        try:
            self.database[self.DOCUMENTS].create_index(
                [("publication_state", 1), ("source.content_hash", 1)]
            )
            self.database[self.PAGES].create_index(
                [("manifest_id", 1), ("page_index", 1)],
                unique=True,
            )
            self.database[self.BLOCKS].create_index(
                [("manifest_id", 1), ("page_index", 1), ("ordinal", 1)],
                unique=True,
            )
            self.database[self.WARNINGS].create_index(
                [("document_id", 1), ("code", 1)]
            )
            self.database[self.MANIFESTS].create_index(
                [("source_blob_id", 1), ("status", 1)]
            )
        except PyMongoError as error:
            raise ExtractionPublicationError(
                "MongoDB extraction indexes could not be prepared"
            ) from error
        self._indexes_ready = True
