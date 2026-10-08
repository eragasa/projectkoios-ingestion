"""Pure canonical reading-evidence to storage read-model projector."""

from __future__ import annotations

from projectkoios.ingestion.base.projector.actionizer import Projector
from projectkoios.ingestion.base.projector.identity.error import (
    ProjectionIdentityError,
)
from projectkoios.ingestion.base.projector.identity.model import (
    ProjectorIdentity,
)
from projectkoios.ingestion.base.projector.payload.error import (
    ProjectionPayloadError,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.collection import (  # noqa: E501
    ReadingEvidenceStorageCollectionDigestInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.manifest import (  # noqa: E501
    ReadingEvidenceCompletionManifest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.json.contract import (  # noqa: E501
    ReadingEvidenceStorageJsonContract,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceStorageProjectionConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.document import (  # noqa: E501
    ReadingEvidenceStorageDocument,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.inventory import (  # noqa: E501
    ReadingEvidenceStorageDocumentInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.kind import (  # noqa: E501
    ReadingEvidenceStorageRecordKind,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.read.model import (  # noqa: E501
    ReadingEvidenceReadModel,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.record.codec import (  # noqa: E501
    ReadingEvidenceStorageRecordCodec,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.source import (  # noqa: E501
    ReadingEvidenceStorageProjectionSource,
)


class ReadingEvidenceStorageProjector(
    Projector[
        ReadingEvidenceStorageProjectionSource,
        ReadingEvidenceStorageProjectionConfiguration,
        ReadingEvidenceReadModel,
    ]
):
    """Derive one complete backend-neutral current-schema read model."""

    __slots__ = ()

    source_type = ReadingEvidenceStorageProjectionSource
    configuration_type = ReadingEvidenceStorageProjectionConfiguration
    projection_type = ReadingEvidenceReadModel
    identity = ProjectorIdentity.create(
        name="reading-evidence-storage-projector",
        version="1.0",
        source_contract=ReadingEvidenceStorageProjectionSource.CONTRACT_NAME,
        configuration_contract=(
            ReadingEvidenceStorageProjectionConfiguration.CONTRACT_NAME
        ),
        projection_contract=ReadingEvidenceReadModel.CONTRACT_NAME,
        schema_id="projectkoios-reading-evidence-storage:v1",
    )

    def project(
        self,
        *,
        sources: tuple[ReadingEvidenceStorageProjectionSource, ...],
        configuration: ReadingEvidenceStorageProjectionConfiguration,
    ) -> ReadingEvidenceReadModel:
        """Project exactly one successful canonical result without I/O."""
        if configuration.schema_version.schema_id != self.identity.schema_id:
            raise ProjectionIdentityError(
                "configuration and projector schema identities differ"
            )
        if len(sources) != 1:
            raise ProjectionPayloadError(
                "storage projection requires exactly one source result"
            )
        result = sources[0].result
        try:
            codec = ReadingEvidenceStorageRecordCodec()
            children = codec.encode_children(
                document=result.document,
                configuration=configuration,
            )
            collection_digests = (
                ReadingEvidenceStorageCollectionDigestInventory.observe(
                    children
                )
            )
            manifest = ReadingEvidenceCompletionManifest(
                schema_version=configuration.schema_version,
                generation_id=configuration.generation_id,
                storage_configuration_id=configuration.configuration_id,
                projection_result_id=result.result_id,
                evidence_document_id=result.document.document_id,
                inventory_id=result.inventory.inventory_id,
                collections=collection_digests,
                completion_state=configuration.completion_state,
            )
            manifest_payload = (
                ReadingEvidenceStorageJsonContract().to_json_value(manifest)
            )
            completion = ReadingEvidenceStorageDocument.create(
                schema_version=configuration.schema_version,
                generation_id=configuration.generation_id,
                evidence_document_id=result.document.document_id,
                kind=ReadingEvidenceStorageRecordKind.COMPLETION,
                semantic_id=manifest.manifest_id,
                payload=manifest_payload,
                maximum_document_bytes=configuration.maximum_document_bytes,
            )
            documents = sorted(
                (*children, completion),
                key=lambda value: (
                    value.kind.collection.value,
                    value.document_id,
                ),
            )
            if len(documents) > configuration.maximum_record_count:
                raise ValueError("read-model record count exceeds its limit")
            return ReadingEvidenceReadModel.create(
                source_projection_result_id=result.result_id,
                configuration_id=configuration.configuration_id,
                schema_version=configuration.schema_version,
                generation_id=configuration.generation_id,
                evidence_document_id=result.document.document_id,
                documents=ReadingEvidenceStorageDocumentInventory(*documents),
            )
        except ProjectionIdentityError, ProjectionPayloadError:
            raise
        except (TypeError, ValueError) as error:
            raise ProjectionPayloadError(
                "canonical reading evidence cannot form the storage schema"
            ) from error
