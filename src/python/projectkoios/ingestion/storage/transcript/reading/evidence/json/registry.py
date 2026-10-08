"""Explicit current-schema typed JSON registry for reading evidence."""

from __future__ import annotations

from enum import Enum
from typing import Any, Final

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.collection import (  # noqa: E501
    ReadingEvidenceStorageCollectionDigest,
    ReadingEvidenceStorageCollectionDigestInventory,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.completion.manifest import (  # noqa: E501
    ReadingEvidenceCompletionManifest,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.schema.version import (  # noqa: E501
    ReadingEvidenceStorageSchemaVersion,
)
from projectkoios.ingestion.transcript.reading.evidence.association.evidence import (  # noqa: E501
    ReadingAssociationEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.association.inventory import (  # noqa: E501
    ReadingAssociationEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.association.role import (  # noqa: E501
    ReadingAssociationRole,
)
from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.basis import (  # noqa: E501
    ReadingTextBlockProjectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.basis import (
    ReadingCaptionSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.disposition import (  # noqa: E501
    ReadingEquationSelectionDisposition,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.gate import (
    ReadingEquationGate,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.status import (
    ReadingEquationRecognitionStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.document import (
    ReadingDocumentProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.evidence import (  # noqa: E501
    ReadingEquationProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.producer.lineage import (  # noqa: E501
    ReadingProducerLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.source import (  # noqa: E501
    ReadingSourceBlockIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.evidence import (  # noqa: E501
    ReadingTableProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.definition import (  # noqa: E501
    ReadingTextTransformation,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.inventory import (  # noqa: E501
    ReadingTextTransformationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.kind import (  # noqa: E501
    ReadingTextTransformationKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.visual.assessment import (  # noqa: E501
    ReadingVisualAssessment,
)
from projectkoios.ingestion.transcript.reading.evidence.label.inventory import (
    ReadingSourceLabelInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.affected import (  # noqa: E501
    ReadingAffectedEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.code import (
    ReadingEvidenceLimitationCode,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.definition import (  # noqa: E501
    ReadingEvidenceLimitation,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.span.evidence import (
    ReadingSourceSpanEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.span.geometry import (
    ReadingBoundingBox,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.status.visual import (
    ReadingVisualEvidenceStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.evidence import (
    ReadingTextStreamEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.kind import (
    ReadingTextStreamKind,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.basis import (  # noqa: E501
    ReadingTextSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.table.boundary import (
    ReadingTableBoundaryKind,
)

TYPE_REGISTRY: Final[dict[str, type[Any]]] = {
    "managed_artifact_reference": ManagedArtifactReference,
    "managed_artifact_reference_inventory": ManagedArtifactReferenceInventory,
    "identity": ReadingEvidenceIdentity,
    "identity_inventory": ReadingEvidenceIdentityInventory,
    "page_location": ReadingPageLocation,
    "bounding_box": ReadingBoundingBox,
    "source_span": ReadingSourceSpanEvidence,
    "source_span_inventory": ReadingSourceSpanEvidenceInventory,
    "association": ReadingAssociationEvidence,
    "association_inventory": ReadingAssociationEvidenceInventory,
    "text_stream": ReadingTextStreamEvidence,
    "text_stream_inventory": ReadingTextStreamEvidenceInventory,
    "text_transformation": ReadingTextTransformation,
    "text_transformation_inventory": ReadingTextTransformationInventory,
    "source_label_inventory": ReadingSourceLabelInventory,
    "source_block_identity_inventory": ReadingSourceBlockIdentityInventory,
    "affected_identity_inventory": ReadingAffectedEvidenceIdentityInventory,
    "producer_lineage": ReadingProducerLineage,
    "visual_assessment": ReadingVisualAssessment,
    "equation_gate": ReadingEquationGate,
    "document_producer": ReadingDocumentProducerEvidence,
    "structured_item_producer": ReadingStructuredItemProducerEvidence,
    "clean_text_producer": ReadingCleanTextProducerEvidence,
    "figure_producer": ReadingFigureProducerEvidence,
    "table_producer": ReadingTableProducerEvidence,
    "equation_producer": ReadingEquationProducerEvidence,
    "caption": ReadingCaptionEvidence,
    "limitation": ReadingEvidenceLimitation,
    "storage_schema_version": ReadingEvidenceStorageSchemaVersion,
    "storage_collection_digest": ReadingEvidenceStorageCollectionDigest,
    "storage_collection_digest_inventory": (
        ReadingEvidenceStorageCollectionDigestInventory
    ),
    "completion_manifest": ReadingEvidenceCompletionManifest,
}
TYPE_TAGS: Final[dict[type[Any], str]] = {
    value: key for key, value in TYPE_REGISTRY.items()
}
ENUM_REGISTRY: Final[dict[str, type[Enum]]] = {
    "managed_artifact_media_type": ManagedArtifactMediaType,
    "identity_kind": ReadingEvidenceIdentityKind,
    "association_role": ReadingAssociationRole,
    "block_kind": ReadingEvidenceBlockKind,
    "text_block_basis": ReadingTextBlockProjectionBasis,
    "caption_basis": ReadingCaptionSelectionBasis,
    "equation_disposition": ReadingEquationSelectionDisposition,
    "equation_status": ReadingEquationRecognitionStatus,
    "structured_item_kind": ReadingStructuredItemKind,
    "transformation_kind": ReadingTextTransformationKind,
    "limitation_code": ReadingEvidenceLimitationCode,
    "review_status": ReadingReviewStatus,
    "visual_status": ReadingVisualEvidenceStatus,
    "text_stream_kind": ReadingTextStreamKind,
    "text_selection_basis": ReadingTextSelectionBasis,
    "table_boundary_kind": ReadingTableBoundaryKind,
    "storage_collection": ReadingEvidenceStorageCollection,
}
ENUM_TAGS: Final[dict[type[Enum], str]] = {
    value: key for key, value in ENUM_REGISTRY.items()
}
SEQUENCE_INVENTORIES: Final[set[type[Any]]] = {
    ManagedArtifactReferenceInventory,
    ReadingSourceSpanEvidenceInventory,
    ReadingAssociationEvidenceInventory,
    ReadingTextStreamEvidenceInventory,
    ReadingTextTransformationInventory,
    ReadingSourceLabelInventory,
    ReadingSourceBlockIdentityInventory,
    ReadingAffectedEvidenceIdentityInventory,
    ReadingEvidenceStorageCollectionDigestInventory,
}
