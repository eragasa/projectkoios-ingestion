"""Pure extraction publication to read-model projector."""

from __future__ import annotations

import json

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
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.json.canonical import CanonicalJsonSerializer
from projectkoios.ingestion.storage.extraction.projection.collection import (
    ExtractionProjectionCollection,
)
from projectkoios.ingestion.storage.extraction.projection.configuration import (
    ExtractionProjectionConfiguration,
)
from projectkoios.ingestion.storage.extraction.projection.document import (
    ExtractionProjectionDocument,
)
from projectkoios.ingestion.storage.extraction.projection.evidence import (
    ExtractionPublicationEvidence,
)
from projectkoios.ingestion.storage.extraction.projection.read.model import (
    ExtractionReadModel,
)


class ExtractionProjectionProjector(
    Projector[
        ExtractionPublicationEvidence,
        ExtractionProjectionConfiguration,
        ExtractionReadModel,
    ]
):
    """Derive the five logical extraction collections without I/O.

    Notes
    -----
    The projector parses exact checksummed publication payloads and emits a
    backend-neutral ``ExtractionReadModel``. It does not open the disk
    journal, select records, authorize access, create indexes, or write to
    MongoDB. Those responsibilities remain with readers, workflow actions, and
    materializers.
    """

    __slots__ = ()

    source_type = ExtractionPublicationEvidence
    configuration_type = ExtractionProjectionConfiguration
    projection_type = ExtractionReadModel
    identity = ProjectorIdentity.create(
        name="extraction-projection-projector",
        version="1.0",
        source_contract=ExtractionPublicationEvidence.CONTRACT_NAME,
        configuration_contract=ExtractionProjectionConfiguration.CONTRACT_NAME,
        projection_contract=ExtractionReadModel.CONTRACT_NAME,
        schema_id="extraction-read-model-v1",
    )

    def project(
        self,
        *,
        sources: tuple[ExtractionPublicationEvidence, ...],
        configuration: ExtractionProjectionConfiguration,
    ) -> ExtractionReadModel:
        """Project exact publication evidence into one immutable read model.

        Parameters
        ----------
        sources
            Canonically ordered journal-record and payload evidence.
        configuration
            Complete schema, identity namespace, and completion-state values.

        Returns
        -------
        ExtractionReadModel
            Canonically ordered documents for all five logical collections.

        Raises
        ------
        ProjectionPayloadError
            If a payload is malformed or cannot form the declared read model.
        ProjectionIdentityError
            If record, payload, or projected document identities disagree.
        """
        if configuration.schema_id != self.identity.schema_id:
            raise ProjectionIdentityError(
                "configuration and projector schema identities differ"
            )
        documents: list[ExtractionProjectionDocument] = []
        for source in sources:
            try:
                documents.extend(
                    self._project_publication(
                        source=source,
                        configuration=configuration,
                    )
                )
            except ProjectionPayloadError, ProjectionIdentityError:
                raise
            except (TypeError, ValueError) as error:
                raise ProjectionPayloadError(
                    "extraction payload cannot form canonical documents"
                ) from error
        ordered = tuple(
            sorted(
                documents,
                key=lambda document: (
                    document.collection.value,
                    document.document_id,
                ),
            )
        )
        keys = tuple(
            (document.collection.value, document.document_id)
            for document in ordered
        )
        # Duplicate keys are identity ambiguity, not malformed JSON. Keeping
        # this distinction lets provider actions stop without suggesting retry.
        if len(keys) != len(set(keys)):
            raise ProjectionIdentityError(
                "projected extraction document identities are not unique"
            )
        try:
            return ExtractionReadModel.create(
                source_evidence_ids=tuple(
                    source.evidence_id for source in sources
                ),
                configuration_id=configuration.configuration_id,
                schema_id=configuration.schema_id,
                documents=ordered,
            )
        except (TypeError, ValueError) as error:
            raise ProjectionPayloadError(
                "extraction publications do not form one valid read model"
            ) from error

    @staticmethod
    def _project_publication(
        *,
        source: ExtractionPublicationEvidence,
        configuration: ExtractionProjectionConfiguration,
    ) -> tuple[ExtractionProjectionDocument, ...]:
        """Project one exact publication payload.

        Parameters
        ----------
        source
            Verified publication record and exact payload bytes.
        configuration
            Deterministic schema and identity configuration.

        Returns
        -------
        tuple[ExtractionProjectionDocument, ...]
            Projected document, page, block, warning, and manifest values.

        Raises
        ------
        ProjectionPayloadError
            If the payload is not canonical extraction-result JSON.
        ProjectionIdentityError
            If payload identities differ from the journal record.
        """
        try:
            value = json.loads(source.payload)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ProjectionPayloadError(
                "extraction publication payload is not canonical JSON"
            ) from error
        if type(value) is not dict or (
            CanonicalJsonSerializer.serialize_text(value).encode("utf-8")
            != source.payload
        ):
            raise ProjectionPayloadError(
                "extraction publication payload is not canonical JSON"
            )
        document = value.get("document")
        manifest = value.get("manifest")
        warnings = value.get("warnings")
        if (
            type(document) is not dict
            or type(manifest) is not dict
            or type(warnings) is not list
        ):
            raise ProjectionPayloadError(
                "publication payload is not an extraction result"
            )
        document_id = document.get("document_id")
        manifest_id = manifest.get("manifest_id")
        pages = document.get("pages")
        if (
            type(document_id) is not str
            or not document_id
            or type(manifest_id) is not str
            or not manifest_id
            or type(pages) is not list
        ):
            raise ProjectionPayloadError(
                "publication payload identities are incomplete"
            )
        if (
            document_id != source.record.document_id
            or manifest_id != source.record.manifest_id
        ):
            raise ProjectionIdentityError(
                "publication record and payload identities differ"
            )

        projected: list[ExtractionProjectionDocument] = []
        page_ids: list[str] = []
        # Child objects are fully derived before the completion document. The
        # immutable read model does not prescribe I/O order, but preserving the
        # hierarchy makes materializer ordering explicit and auditable.
        for page in pages:
            page_document, block_documents = (
                ExtractionProjectionProjector._project_page(
                    document_id=document_id,
                    manifest_id=manifest_id,
                    page=page,
                    publication_digest=source.record.payload_sha256,
                    configuration=configuration,
                )
            )
            page_ids.append(page_document.document_id)
            projected.extend(block_documents)
            projected.append(page_document)

        for warning in warnings:
            if (
                type(warning) is not dict
                or type(warning.get("warning_id")) is not str
                or not warning["warning_id"]
            ):
                raise ProjectionPayloadError(
                    "extraction warning projection is invalid"
                )
            warning_document = dict(warning)
            warning_document.update(
                {
                    "_id": stable_id(
                        configuration.warning_identity_namespace,
                        configuration.identity_version,
                        manifest_id,
                        warning["warning_id"],
                    ),
                    "document_id": document_id,
                    "manifest_id": manifest_id,
                    "publication_digest": source.record.payload_sha256,
                }
            )
            projected.append(
                ExtractionProjectionDocument.create(
                    collection=ExtractionProjectionCollection.WARNINGS,
                    value=warning_document,
                )
            )

        manifest_document = dict(manifest)
        manifest_document.update(
            {
                "_id": manifest_id,
                "document_id": document_id,
                "publication_digest": source.record.payload_sha256,
            }
        )
        projected.append(
            ExtractionProjectionDocument.create(
                collection=ExtractionProjectionCollection.MANIFESTS,
                value=manifest_document,
            )
        )
        # Pages and blocks are replaced by stable references so a database can
        # query the hierarchy without duplicating the entire extraction graph.
        document_manifest = {
            key: item for key, item in document.items() if key != "pages"
        }
        document_manifest.update(
            {
                "_id": manifest_id,
                "document_id": document_id,
                "manifest_id": manifest_id,
                "page_ids": page_ids,
                "publication_digest": source.record.payload_sha256,
                "publication_state": configuration.completion_state,
            }
        )
        projected.append(
            ExtractionProjectionDocument.create(
                collection=ExtractionProjectionCollection.DOCUMENTS,
                value=document_manifest,
            )
        )
        return tuple(projected)

    @staticmethod
    def _project_page(
        *,
        document_id: str,
        manifest_id: str,
        page: object,
        publication_digest: str,
        configuration: ExtractionProjectionConfiguration,
    ) -> tuple[
        ExtractionProjectionDocument,
        tuple[ExtractionProjectionDocument, ...],
    ]:
        """Project one page and all of its blocks.

        Parameters
        ----------
        document_id
            Stable extracted-document identity.
        manifest_id
            Stable extraction-manifest identity.
        page
            Canonical JSON page object from the publication payload.
        publication_digest
            SHA-256 digest of the authoritative payload.
        configuration
            Deterministic schema and identity configuration.

        Returns
        -------
        tuple
            The projected page followed by its projected block values.

        Raises
        ------
        ProjectionPayloadError
            If the page or any block lacks required structure.
        """
        if (
            type(page) is not dict
            or type(page.get("page_index")) is not int
            or page["page_index"] < 0
        ):
            raise ProjectionPayloadError(
                "extraction page projection is invalid"
            )
        page_index = page["page_index"]
        blocks = page.get("blocks")
        if type(blocks) is not list:
            raise ProjectionPayloadError("extraction page blocks are invalid")
        page_id = stable_id(
            configuration.page_identity_namespace,
            configuration.identity_version,
            document_id,
            manifest_id,
            page_index,
        )
        block_ids: list[str] = []
        block_documents: list[ExtractionProjectionDocument] = []
        for ordinal, block in enumerate(blocks):
            if (
                type(block) is not dict
                or type(block.get("block_id")) is not str
                or not block["block_id"]
            ):
                raise ProjectionPayloadError(
                    "extraction block projection is invalid"
                )
            block_document = dict(block)
            block_document.update(
                {
                    "_id": stable_id(
                        configuration.block_identity_namespace,
                        configuration.identity_version,
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
            projected_block = ExtractionProjectionDocument.create(
                collection=ExtractionProjectionCollection.BLOCKS,
                value=block_document,
            )
            block_documents.append(projected_block)
            block_ids.append(projected_block.document_id)
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
        return (
            ExtractionProjectionDocument.create(
                collection=ExtractionProjectionCollection.PAGES,
                value=page_document,
            ),
            tuple(block_documents),
        )
