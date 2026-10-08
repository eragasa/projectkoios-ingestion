"""Pure current-schema reading-evidence read-model verification."""

from __future__ import annotations

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.collection import (  # noqa: E501
    ReadingEvidenceStorageCollectionDigestInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.manifest import (  # noqa: E501
    ReadingEvidenceCompletionManifest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.json.contract import (  # noqa: E501
    ReadingEvidenceStorageJsonContract,
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
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)


class ReadingEvidenceReadModelVerifier:
    """Strictly reconstruct and verify one completed current read model."""

    __slots__ = ()

    IMPLEMENTATION_ID = "reading-evidence-read-model-verifier:1.0"

    def verify(
        self,
        *,
        request: ReadingEvidenceSourceRequest,
        read_model: ReadingEvidenceReadModel,
        provider_implementation_id: str,
    ) -> ReadingEvidenceSourceResult:
        """Return one backend-neutral source result after exact verification."""
        if type(request) is not ReadingEvidenceSourceRequest:
            raise TypeError("request has an unsupported type")
        if type(read_model) is not ReadingEvidenceReadModel:
            raise TypeError("read_model has an unsupported type")
        if (
            type(provider_implementation_id) is not str
            or not provider_implementation_id
            or len(provider_implementation_id.encode("utf-8")) > 512
        ):
            raise ValueError("provider_implementation_id is invalid")
        if (
            read_model.schema_version
            != ReadingEvidenceStorageSchemaVersion.current()
        ):
            raise ValueError("read model does not use the current schema")
        if len(read_model.documents) > request.maximum_provider_record_count:
            raise ValueError("provider record count exceeds request bound")
        if (
            read_model.evidence_document_id != request.document_id
            or read_model.source_projection_result_id
            != request.projection_result_id
        ):
            raise ValueError("read-model scope differs from source request")
        completions = read_model.documents.for_kind(
            ReadingEvidenceStorageRecordKind.COMPLETION
        )
        if len(completions) != 1:
            raise ValueError("read model requires exactly one completion")
        completion = completions[0]
        manifest = ReadingEvidenceStorageJsonContract().decode_as(
            completion.payload(), ReadingEvidenceCompletionManifest
        )
        if completion.semantic_id != manifest.manifest_id:
            raise ValueError("completion semantic identity differs")
        if (
            manifest.schema_version != read_model.schema_version
            or manifest.generation_id != read_model.generation_id
            or manifest.storage_configuration_id != read_model.configuration_id
            or manifest.projection_result_id != request.projection_result_id
            or manifest.evidence_document_id != request.document_id
            or manifest.inventory_id != request.inventory_id
        ):
            raise ValueError("completion manifest scope differs")
        children = ReadingEvidenceStorageDocumentInventory(
            *(
                value
                for value in read_model.documents
                if value.kind is not ReadingEvidenceStorageRecordKind.COMPLETION
            )
        )
        observed_collections = (
            ReadingEvidenceStorageCollectionDigestInventory.observe(children)
        )
        if observed_collections != manifest.collections:
            raise ValueError("completion collection evidence differs")
        document = ReadingEvidenceStorageRecordCodec().decode_children(children)
        inventory = ReadingEvidenceInventory.observe(document)
        if (
            document.document_id != request.document_id
            or inventory.inventory_id != request.inventory_id
            or inventory.inventory_id != manifest.inventory_id
        ):
            raise ValueError("reconstructed canonical identities differ")
        measures = inventory.measures
        if (
            measures.page_count > request.maximum_page_count
            or measures.block_count > request.maximum_block_count
            or measures.artifact_count > request.maximum_artifact_count
        ):
            raise ValueError("canonical reading evidence exceeds request bound")
        verification_id = stable_id(
            "reading-evidence-read-model-verification",
            self.IMPLEMENTATION_ID,
            provider_implementation_id,
            request.request_id,
            read_model.projection_id,
            read_model.canonical_sha256,
            manifest.manifest_id,
            inventory.inventory_id.value,
        )
        return ReadingEvidenceSourceResult(
            request=request,
            document=document,
            inventory=inventory,
            projection_result_id=manifest.projection_result_id,
            provider_implementation_id=provider_implementation_id,
            provider_verification_id=verification_id,
        )
