"""MongoDB projection of authoritative extraction publications."""

from __future__ import annotations

from typing import Any, ClassVar

from projectkoios.ingestion.base.projector.error import ProjectionContractError
from projectkoios.ingestion.base.projector.identity_error import (
    ProjectionIdentityError,
)
from projectkoios.ingestion.base.projector.payload_error import (
    ProjectionPayloadError,
)
from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materialization_error import (  # noqa: E501
    MongoExtractionProjectionMaterializationError,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materializer import (  # noqa: E501
    MongoExtractionProjectionMaterializer,
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
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.projector import (
    ExtractionProjectionProjector,
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

    DOCUMENTS: ClassVar[str] = MongoExtractionProjectionMaterializer.DOCUMENTS
    PAGES: ClassVar[str] = MongoExtractionProjectionMaterializer.PAGES
    BLOCKS: ClassVar[str] = MongoExtractionProjectionMaterializer.BLOCKS
    WARNINGS: ClassVar[str] = MongoExtractionProjectionMaterializer.WARNINGS
    MANIFESTS: ClassVar[str] = MongoExtractionProjectionMaterializer.MANIFESTS
    PROJECTOR: ClassVar[ExtractionProjectionProjector] = (
        ExtractionProjectionProjector()
    )
    PROJECTION_CONFIGURATION: ClassVar[ExtractionProjectionConfiguration] = (
        ExtractionProjectionConfiguration.v1()
    )

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
        self.materializer = MongoExtractionProjectionMaterializer(
            database=database
        )
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
        self._project_and_materialize(record)
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
            self._project_and_materialize(record)
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
                projected += self._project_and_materialize(selected)
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
            elif isinstance(
                cause, MongoExtractionProjectionMaterializationError
            ):
                code = cause.code
                disposition = ExtractionActionDisposition.STOP_INVALID_EVIDENCE
            elif isinstance(cause, ProjectionIdentityError):
                code = "projection_identity_differs"
                disposition = (
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                )
            elif isinstance(cause, ProjectionPayloadError):
                code = "publication_payload_invalid"
                disposition = ExtractionActionDisposition.STOP_INVALID_EVIDENCE
            elif isinstance(cause, ProjectionContractError):
                code = "projection_contract_invalid"
                disposition = ExtractionActionDisposition.STOP_INVALID_EVIDENCE
            else:
                code = "publication_evidence_invalid"
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

    def _project_and_materialize(
        self,
        record: ExtractionPublicationRecord,
    ) -> int:
        """Project and materialize one exact authoritative journal record.

        Parameters
        ----------
        record
            Validated journal record whose exact payload remains on disk.

        Returns
        -------
        int
            One when the root document is newly created; zero on exact replay.

        Raises
        ------
        ExtractionPublicationError
            If evidence, projection, index preparation, or materialization
            fails.

        Notes
        -----
        This adapter method composes separate responsibilities. The disk reader
        supplies complete immutable evidence, the projector performs the pure
        transformation, and the MongoDB materializer performs writes.
        """
        payload = self.journal.payload(record)
        try:
            evidence = ExtractionPublicationEvidence.create(
                record=record,
                payload=payload,
            )
            request = ProjectionRequest.create(
                sources=(evidence,),
                configuration=self.PROJECTION_CONFIGURATION,
            )
            read_model = self.PROJECTOR.action(request=request).projection
        except (TypeError, ValueError, ProjectionContractError) as error:
            raise ExtractionPublicationError(
                "extraction publication projection evidence is invalid"
            ) from error

        # Index readiness remains an adapter concern and is intentionally not
        # hidden inside either the pure projector or the document materializer.
        self._ensure_indexes()
        try:
            created_roots = self.materializer.materialize(read_model=read_model)
        except MongoExtractionProjectionMaterializationError as error:
            # Preserve PyMongo's typed cause for existing provider-action
            # disposition mapping while retaining the materializer's category.
            cause = error.__cause__
            if isinstance(cause, PyMongoError):
                raise ExtractionPublicationError(str(error)) from cause
            raise ExtractionPublicationError(str(error)) from error
        if created_roots not in (0, 1):
            raise ExtractionPublicationError(
                "single publication produced an invalid root-document count"
            )
        return created_roots

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
