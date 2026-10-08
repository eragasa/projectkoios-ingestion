"""Semantic fixture owner for reading-evidence foundation contracts."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.artifact.managed.media.type import (
    ManagedArtifactMediaType,
)
from projectkoios.ingestion.artifact.managed.reference import (
    ManagedArtifactReference,
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
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.producer.lineage import (  # noqa: E501
    ReadingProducerLineage,
)
from projectkoios.ingestion.transcript.reading.evidence.input.visual.assessment import (  # noqa: E501
    ReadingVisualAssessment,
)
from projectkoios.ingestion.transcript.reading.evidence.label.inventory import (
    ReadingSourceLabelInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.definition import (  # noqa: E501
    ReadingTextSelection,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceFoundationFixture:
    """Build deterministic exact values shared by foundation tests."""

    digest: str = "a" * 64

    def identity(
        self,
        kind: ReadingEvidenceIdentityKind,
        token: str,
    ) -> ReadingEvidenceIdentity:
        """Return one explicit typed external identity."""
        return ReadingEvidenceIdentity(kind=kind, value=f"{kind.value}:{token}")

    def page(self, index: int = 0) -> ReadingPageLocation:
        """Return one canonical page location."""
        return ReadingPageLocation(
            physical_page_index=index,
            printed_page_label=str(index + 1),
        )

    def artifact(
        self,
        *,
        media_type: ManagedArtifactMediaType = (
            ManagedArtifactMediaType.IMAGE_PNG
        ),
    ) -> ManagedArtifactReference:
        """Return one exact managed artifact reference."""
        return ManagedArtifactReference(
            sha256=self.digest,
            byte_length=128,
            media_type=media_type,
        )

    def artifact_inventory(self) -> ManagedArtifactReferenceInventory:
        """Return one nonempty managed artifact inventory."""
        return ManagedArtifactReferenceInventory(self.artifact())

    def native_streams(
        self,
        *,
        page: ReadingPageLocation | None = None,
    ) -> ReadingTextStreamEvidenceInventory:
        """Return exact native-only stream evidence."""
        location = self.page() if page is None else page
        native = ReadingTextStreamEvidence(
            kind=ReadingTextStreamKind.NATIVE,
            page_location=location,
            text="Native page text.",
            upstream_id=self.identity(
                ReadingEvidenceIdentityKind.EXTRACTION_RESULT, "native"
            ),
            producer_id=self.identity(
                ReadingEvidenceIdentityKind.PRODUCER, "native"
            ),
            composition_id=None,
            automated=True,
            accepted=False,
            review_status=ReadingReviewStatus.UNREVIEWED,
        )
        return ReadingTextStreamEvidenceInventory(native)

    def native_selection(
        self,
        streams: ReadingTextStreamEvidenceInventory,
    ) -> ReadingTextSelection:
        """Select exact native evidence."""
        native = next(iter(streams))
        return ReadingTextSelection(
            streams=streams,
            selected_stream_id=native.stream_id,
            basis=ReadingTextSelectionBasis.NATIVE_EXACT,
        )

    def text_source_spans(
        self,
        *,
        page: ReadingPageLocation | None = None,
    ) -> ReadingSourceSpanEvidenceInventory:
        """Return one exact source span for clean text evidence."""
        location = self.page() if page is None else page
        span = ReadingSourceSpanEvidence(
            source_id=self.identity(ReadingEvidenceIdentityKind.SOURCE, "book"),
            page_location=location,
            start_offset=0,
            end_offset=12,
        )
        return ReadingSourceSpanEvidenceInventory(span)

    def source_spans(
        self,
        *,
        source_object_id: ReadingEvidenceIdentity,
        page: ReadingPageLocation | None = None,
    ) -> ReadingSourceSpanEvidenceInventory:
        """Return one exact visual source span."""
        location = self.page() if page is None else page
        span = ReadingSourceSpanEvidence(
            source_id=self.identity(ReadingEvidenceIdentityKind.SOURCE, "book"),
            page_location=location,
            source_object_id=source_object_id,
            bounding_box=ReadingBoundingBox(0.1, 0.2, 0.3, 0.4),
        )
        return ReadingSourceSpanEvidenceInventory(span)

    def associations(
        self,
        *,
        page: ReadingPageLocation | None = None,
    ) -> ReadingAssociationEvidenceInventory:
        """Return one exact caption association."""
        location = self.page() if page is None else page
        source_object_id = self.identity(
            ReadingEvidenceIdentityKind.SOURCE_OBJECT, "caption"
        )
        span = ReadingSourceSpanEvidence(
            source_id=self.identity(ReadingEvidenceIdentityKind.SOURCE, "book"),
            page_location=location,
            source_object_id=source_object_id,
            start_offset=0,
            end_offset=12,
        )
        association = ReadingAssociationEvidence(
            role=ReadingAssociationRole.CAPTION,
            text="Figure title",
            source_block_ids=ReadingEvidenceIdentityInventory(
                ReadingEvidenceIdentityKind.SOURCE_BLOCK,
                self.identity(
                    ReadingEvidenceIdentityKind.SOURCE_BLOCK, "caption"
                ),
            ),
            source_spans=ReadingSourceSpanEvidenceInventory(span),
            producer_association_id=self.identity(
                ReadingEvidenceIdentityKind.ASSOCIATION, "caption"
            ),
        )
        return ReadingAssociationEvidenceInventory(association)

    def labels(self) -> ReadingSourceLabelInventory:
        """Return one canonical source-label inventory."""
        return ReadingSourceLabelInventory("Figure 1")

    def producer_lineage(
        self,
        *,
        source_object_id: ReadingEvidenceIdentity,
        page: ReadingPageLocation | None = None,
        source_spans: ReadingSourceSpanEvidenceInventory | None = None,
        warning_ids: ReadingEvidenceIdentityInventory | None = None,
        producer_token: str = "visual",
    ) -> ReadingProducerLineage:
        """Return exact shared producer lineage for one visual object."""
        location = self.page() if page is None else page
        return ReadingProducerLineage(
            source_object_id=source_object_id,
            page_location=location,
            source_labels=self.labels(),
            source_spans=(
                self.source_spans(
                    source_object_id=source_object_id,
                    page=location,
                )
                if source_spans is None
                else source_spans
            ),
            warning_ids=(
                self.warning_ids() if warning_ids is None else warning_ids
            ),
            artifacts=self.artifact_inventory(),
            producer_id=self.identity(
                ReadingEvidenceIdentityKind.PRODUCER, producer_token
            ),
            producer_version="1",
        )

    def visual_assessment(
        self,
        *,
        page: ReadingPageLocation | None = None,
        confidence: float = 0.9,
        visual_status: ReadingVisualEvidenceStatus = (
            ReadingVisualEvidenceStatus.PROPOSED
        ),
        review_status: ReadingReviewStatus = ReadingReviewStatus.UNREVIEWED,
    ) -> ReadingVisualAssessment:
        """Return exact shared visual assessment evidence."""
        location = self.page() if page is None else page
        return ReadingVisualAssessment(
            associations=self.associations(page=location),
            confidence=confidence,
            visual_status=visual_status,
            review_status=review_status,
        )

    def warning_ids(self) -> ReadingEvidenceIdentityInventory:
        """Return an empty typed warning identity inventory."""
        return ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.WARNING
        )
