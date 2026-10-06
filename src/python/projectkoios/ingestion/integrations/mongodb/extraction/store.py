"""MongoDB projection of authoritative extraction publications."""

from __future__ import annotations

from typing import Any, ClassVar

from projectkoios.ingestion.base.materializer.error import (
    MaterializationContractError,
)
from projectkoios.ingestion.base.materializer.identity.error import (
    MaterializationIdentityError,
)
from projectkoios.ingestion.base.pipeline.error import (  # noqa: E501
    PipelineContractError,
)
from projectkoios.ingestion.base.projector.error import ProjectionContractError
from projectkoios.ingestion.base.projector.identity.error import (
    ProjectionIdentityError,
)
from projectkoios.ingestion.base.projector.payload.error import (
    ProjectionPayloadError,
)
from projectkoios.ingestion.identity import canonical_json
from projectkoios.ingestion.integrations.disk.extraction.store import (
    DiskExtractionPublicationStore,
)
from projectkoios.ingestion.integrations.mongodb.extraction.index.readiness.backend import (  # noqa: E501
    MongoExtractionProjectionIndexReadinessBackend,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materialization.error import (  # noqa: E501
    MongoExtractionProjectionMaterializationError,
)
from projectkoios.ingestion.integrations.mongodb.extraction.materializer import (  # noqa: E501
    MongoExtractionProjectionMaterializer,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.storage.extraction.actions.disposition import (
    ExtractionActionDisposition,
)
from projectkoios.ingestion.storage.extraction.base import (
    AbstractExtractionPublicationStore,
)
from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.backend.error import (  # noqa: E501
    ExtractionProjectionIndexReadinessBackendError,
)
from projectkoios.ingestion.storage.extraction.projection.index.readiness.configuration import (  # noqa: E501
    ExtractionProjectionIndexReadinessConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.collection import (  # noqa: E501
    ExtractionProjectionCollectionInventory,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.configuration import (  # noqa: E501
    ExtractionProjectionInventoryConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.reader.base import (  # noqa: E501
    ExtractionProjectionInventoryReader,
)
from projectkoios.ingestion.storage.extraction.projection.inventory.reader.error import (  # noqa: E501
    ExtractionProjectionInventoryReaderError,
)
from projectkoios.ingestion.storage.extraction.projection.pipeline.actionizer import (  # noqa: E501
    ExtractionProjectionMaterializationPipeline,
)
from projectkoios.ingestion.storage.extraction.projection.pipeline.configuration import (  # noqa: E501
    ExtractionProjectionPipelineConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.pipeline.request import (  # noqa: E501
    ExtractionProjectionPipelineRequest,
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
from projectkoios.ingestion.storage.extraction.recovery.subset.backend.base import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryBackend,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.backend.error import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryBackendError,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.evidence import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryEvidence,
)
from projectkoios.ingestion.storage.extraction.recovery.subset.request import (  # noqa: E501
    ExtractionProjectionSubsetRecoveryRequest,
)
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

MongoDocument = dict[str, Any]


class MongoExtractionPublicationStore(
    AbstractExtractionPublicationStore,
    ExtractionProjectionInventoryReader,
    ExtractionProjectionSubsetRecoveryBackend,
):
    """Idempotent MongoDB read projection backed by a disk journal."""

    PROJECTION_CONFIGURATION: ClassVar[ExtractionProjectionConfiguration] = (
        ExtractionProjectionConfiguration.v1()
    )
    MATERIALIZATION_CONFIGURATION: ClassVar[
        ExtractionProjectionMaterializationConfiguration
    ] = ExtractionProjectionMaterializationConfiguration.mongodb_v1()
    PIPELINE_CONFIGURATION: ClassVar[
        ExtractionProjectionPipelineConfiguration
    ] = ExtractionProjectionPipelineConfiguration.create(
        projection_configuration=PROJECTION_CONFIGURATION,
        materialization_configuration=MATERIALIZATION_CONFIGURATION,
    )
    INVENTORY_CONFIGURATION: ClassVar[
        ExtractionProjectionInventoryConfiguration
    ] = ExtractionProjectionInventoryConfiguration.mongodb_v1()
    INDEX_READINESS_CONFIGURATION: ClassVar[
        ExtractionProjectionIndexReadinessConfiguration
    ] = ExtractionProjectionIndexReadinessConfiguration.mongodb_v1()
    DOCUMENTS: ClassVar[str] = (
        MATERIALIZATION_CONFIGURATION.documents_collection
    )
    PAGES: ClassVar[str] = MATERIALIZATION_CONFIGURATION.pages_collection
    BLOCKS: ClassVar[str] = MATERIALIZATION_CONFIGURATION.blocks_collection
    WARNINGS: ClassVar[str] = MATERIALIZATION_CONFIGURATION.warnings_collection
    MANIFESTS: ClassVar[str] = (
        MATERIALIZATION_CONFIGURATION.manifests_collection
    )

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        journal: DiskExtractionPublicationStore,
        projection_target: ExtractionProjectionTargetIdentity,
        default_write_authority_id: str,
    ) -> None:
        if type(journal) is not DiskExtractionPublicationStore:
            raise TypeError("journal must be a DiskExtractionPublicationStore")
        if type(projection_target) is not ExtractionProjectionTargetIdentity:
            raise TypeError("projection_target has the wrong contract")
        if (
            type(default_write_authority_id) is not str
            or not default_write_authority_id
        ):
            raise ValueError("default write authority must be non-empty")
        self.database = database
        self.journal = journal
        self.projection_target = projection_target
        self.default_write_authority_id = default_write_authority_id
        self.index_readiness_backend = (
            MongoExtractionProjectionIndexReadinessBackend(
                database=database,
                configured_target=projection_target,
                configured_configuration=self.INDEX_READINESS_CONFIGURATION,
            )
        )
        self.materializer = MongoExtractionProjectionMaterializer(
            database=database,
            configured_target=projection_target,
        )
        self.projection_pipeline = ExtractionProjectionMaterializationPipeline(
            materializer=self.materializer,
        )
        self.projection_reference = projection_target.target_id
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
        self._apply_publication_record(
            record,
            authority_id=self.default_write_authority_id,
        )
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
            self._apply_publication_record(
                record,
                authority_id=self.default_write_authority_id,
            )
        return ExtractionProjectionRecoveryResult(
            request_id=request.request_id,
            observed_records=len(records),
            projected_records=len(records),
            last_journal_sequence=records[-1].sequence if records else None,
        )

    def recover_subset(
        self,
        *,
        request: ExtractionProjectionSubsetRecoveryRequest,
    ) -> ExtractionProjectionSubsetRecoveryEvidence:
        """Recover all and only the exact journal records in the request."""

        if not isinstance(request, ExtractionProjectionSubsetRecoveryRequest):
            raise TypeError(
                "request must be an ExtractionProjectionSubsetRecoveryRequest"
            )
        if request.projection_reference != self.projection_reference:
            raise ExtractionProjectionSubsetRecoveryBackendError(
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
            raise ExtractionProjectionSubsetRecoveryBackendError(
                code="authoritative_journal_invalid",
                disposition=(ExtractionActionDisposition.STOP_INVALID_EVIDENCE),
                message="authoritative extraction journal is invalid",
            ) from error
        head = records[-1].record_sha256 if records else None
        if (
            len(records) != request.expected_journal_record_count
            or head != request.expected_journal_head_sha256
        ):
            raise ExtractionProjectionSubsetRecoveryBackendError(
                code="authoritative_journal_identity_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="authoritative extraction journal identity differs",
            )
        for subset_record in request.subset_records:
            if records[subset_record.sequence - 1] != subset_record:
                raise ExtractionProjectionSubsetRecoveryBackendError(
                    code="subset_publication_record_differs",
                    disposition=(
                        ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                    ),
                    message="subset publication record differs",
                )
        before = self._subset_inventory(request)
        if request.require_empty_projection and any(
            item.document_count for item in before
        ):
            raise ExtractionProjectionSubsetRecoveryBackendError(
                code="projection_is_not_empty",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="subset recovery requires an empty projection",
            )
        projected = 0
        try:
            for subset_record in request.subset_records:
                projected += self._apply_publication_record(
                    subset_record,
                    authority_id=request.authority_id,
                )
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
                cause, ExtractionProjectionIndexReadinessBackendError
            ):
                code = cause.code
                disposition = cause.disposition
            elif isinstance(
                cause, MongoExtractionProjectionMaterializationError
            ):
                code = cause.code
                disposition = ExtractionActionDisposition.STOP_INVALID_EVIDENCE
            elif isinstance(cause, MaterializationIdentityError):
                code = "materialization_identity_differs"
                disposition = (
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                )
            elif isinstance(cause, MaterializationContractError):
                code = "materialization_contract_invalid"
                disposition = ExtractionActionDisposition.STOP_INVALID_EVIDENCE
            elif isinstance(cause, PipelineContractError):
                code = "projection_pipeline_contract_invalid"
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
            raise ExtractionProjectionSubsetRecoveryBackendError(
                code=code,
                disposition=disposition,
                message="extraction projection subset recovery failed",
            ) from error
        collections = self._subset_inventory(request)
        return ExtractionProjectionSubsetRecoveryEvidence.create(
            observed_journal_record_count=len(records),
            observed_journal_head_sha256=head,
            subset_record_count=len(request.subset_records),
            projected_record_count=projected,
            unchanged_record_count=len(request.subset_records) - projected,
            last_subset_sequence=(
                request.subset_records[-1].sequence
                if request.subset_records
                else None
            ),
            collections=collections,
        )

    def _subset_inventory(
        self,
        request: ExtractionProjectionSubsetRecoveryRequest,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        try:
            return self.read_inventory(
                target=self.projection_target,
                configuration=self.INVENTORY_CONFIGURATION,
                authority_id=request.authority_id,
            )
        except ExtractionProjectionInventoryReaderError as error:
            raise ExtractionProjectionSubsetRecoveryBackendError(
                code=error.code,
                disposition=error.disposition,
                message="subset recovery projection inventory failed",
            ) from error

    def read_inventory(
        self,
        *,
        target: ExtractionProjectionTargetIdentity,
        configuration: ExtractionProjectionInventoryConfiguration,
        authority_id: str,
    ) -> tuple[ExtractionProjectionCollectionInventory, ...]:
        """Return complete canonical-content digests for owned collections."""

        if target != self.projection_target:
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
        if configuration != self.INVENTORY_CONFIGURATION:
            raise ExtractionProjectionInventoryReaderError(
                code="projection_inventory_configuration_differs",
                disposition=(
                    ExtractionActionDisposition.STOP_AMBIGUOUS_EVIDENCE
                ),
                message="projection inventory configuration differs",
            )
        collections: list[ExtractionProjectionCollectionInventory] = []
        for collection_name in configuration.collection_names:
            members: list[tuple[str, str]] = []
            try:
                cursor = self.database[collection_name].find({})
                for document in cursor:
                    identity = document.get("_id")
                    if type(identity) is not str or not identity:
                        raise ExtractionProjectionInventoryReaderError(
                            code="projection_inventory_document_invalid",
                            disposition=(
                                ExtractionActionDisposition.STOP_INVALID_EVIDENCE
                            ),
                            message="projection inventory document is invalid",
                        )
                    try:
                        content_sha256 = SHA256Fingerprinter.fingerprint(
                            content=canonical_json(document).encode("utf-8")
                        )
                    except (TypeError, ValueError) as error:
                        raise ExtractionProjectionInventoryReaderError(
                            code="projection_inventory_document_invalid",
                            disposition=(
                                ExtractionActionDisposition.STOP_INVALID_EVIDENCE
                            ),
                            message="projection inventory document is invalid",
                        ) from error
                    members.append((identity, content_sha256))
                    if len(members) > (
                        configuration.maximum_documents_per_collection
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

    def _apply_publication_record(
        self,
        record: ExtractionPublicationRecord,
        *,
        authority_id: str,
    ) -> int:
        """Project and materialize one exact authoritative journal record.

        Parameters
        ----------
        record
            Validated journal record whose exact payload remains on disk.
        authority_id
            Exact authority identity presented to the materializer stage.

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
        The adapter reads authoritative bytes and establishes index readiness.
        The typed pipeline owns synchronous projector-to-materializer
        composition without owning workflow scheduling, retries, or state.
        """
        payload = self.journal.payload(record)
        try:
            evidence = ExtractionPublicationEvidence.create(
                record=record,
                payload=payload,
            )
            pipeline_request = ExtractionProjectionPipelineRequest.create(
                source=evidence,
                target=self.projection_target,
                configuration=self.PIPELINE_CONFIGURATION,
                authority_id=authority_id,
            )
        except (TypeError, ValueError) as error:
            raise ExtractionPublicationError(
                "extraction publication pipeline evidence is invalid"
            ) from error

        # Index readiness is adapter setup rather than a pipeline stage. It has
        # separate evidence and never changes the projected document values.
        self._ensure_indexes_once(authority_id=authority_id)
        try:
            materialization = self.projection_pipeline.action(
                request=pipeline_request
            ).evidence
        except (
            PipelineContractError,
            ProjectionContractError,
            MaterializationContractError,
            MongoExtractionProjectionMaterializationError,
        ) as error:
            # Preserve PyMongo's typed cause for existing provider-action
            # disposition mapping while retaining the materializer's category.
            cause = error.__cause__
            if isinstance(cause, PyMongoError):
                raise ExtractionPublicationError(str(error)) from cause
            raise ExtractionPublicationError(str(error)) from error
        document_evidence = next(
            item
            for item in materialization.collections
            if item.collection is ExtractionProjectionCollection.DOCUMENTS
        )
        if (
            document_evidence.created_document_count
            + document_evidence.unchanged_document_count
            != 1
        ):
            raise ExtractionPublicationError(
                "single publication produced an invalid root-document count"
            )
        return document_evidence.created_document_count

    def _ensure_indexes_once(self, *, authority_id: str) -> None:
        if self._indexes_ready:
            return
        try:
            self.index_readiness_backend.ensure_index_readiness(
                target=self.projection_target,
                configuration=self.INDEX_READINESS_CONFIGURATION,
                authority_id=authority_id,
            )
        except ExtractionProjectionIndexReadinessBackendError as error:
            raise ExtractionPublicationError(
                "MongoDB extraction indexes could not be prepared"
            ) from error
        self._indexes_ready = True
