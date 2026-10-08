"""Shared exact lineage for visual and equation producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.artifact.managed.inventory import (
    ManagedArtifactReferenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.label.inventory import (
    ReadingSourceLabelInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)


@dataclass(frozen=True, slots=True)
class ReadingProducerLineage:
    """Bind producer identity to one page object and exact source evidence."""

    source_object_id: ReadingEvidenceIdentity
    page_location: ReadingPageLocation
    source_labels: ReadingSourceLabelInventory
    source_spans: ReadingSourceSpanEvidenceInventory
    warning_ids: ReadingEvidenceIdentityInventory
    artifacts: ManagedArtifactReferenceInventory
    producer_id: ReadingEvidenceIdentity
    producer_version: str
    lineage_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        roles = (
            (
                self.source_object_id,
                ReadingEvidenceIdentityKind.SOURCE_OBJECT,
                "source_object_id",
            ),
            (
                self.producer_id,
                ReadingEvidenceIdentityKind.PRODUCER,
                "producer_id",
            ),
        )
        for value, kind, name in roles:
            if (
                type(value) is not ReadingEvidenceIdentity
                or value.kind is not kind
            ):
                raise TypeError(f"{name} has the wrong identity role")
        if type(self.page_location) is not ReadingPageLocation:
            raise TypeError("page_location must be ReadingPageLocation")
        if type(self.source_labels) is not ReadingSourceLabelInventory:
            raise TypeError("source_labels must be ReadingSourceLabelInventory")
        if type(
            self.source_spans
        ) is not ReadingSourceSpanEvidenceInventory or (not self.source_spans):
            raise ReadingEvidenceError("producer lineage requires source spans")
        if any(
            span.page_location != self.page_location
            or span.source_object_id != self.source_object_id
            for span in self.source_spans
        ):
            raise ReadingEvidenceError(
                "producer source span lineage is inconsistent"
            )
        if type(self.warning_ids) is not ReadingEvidenceIdentityInventory or (
            self.warning_ids.kind is not ReadingEvidenceIdentityKind.WARNING
        ):
            raise TypeError("warning_ids must be a warning identity inventory")
        warnings = set(self.warning_ids)
        if any(
            span.geometry_warning_id is not None
            and span.geometry_warning_id not in warnings
            for span in self.source_spans
        ):
            raise ReadingEvidenceError(
                "producer geometry warning is absent from warning_ids"
            )
        if type(self.artifacts) is not ManagedArtifactReferenceInventory:
            raise TypeError(
                "artifacts must be ManagedArtifactReferenceInventory"
            )
        READING_EVIDENCE_LIMITS.require_text(
            self.producer_version,
            "producer_version",
            maximum_bytes=(
                READING_EVIDENCE_LIMITS.maximum_producer_version_bytes
            ),
        )
        object.__setattr__(
            self,
            "lineage_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.PRODUCER_LINEAGE,
                prefix="reading-producer-lineage",
                material={
                    "source_object_id": self.source_object_id.value,
                    "page_location_id": self.page_location.location_id.value,
                    "source_labels": self.source_labels.identity_material(),
                    "source_spans": self.source_spans.identity_material(),
                    "warning_ids": self.warning_ids.identity_material(),
                    "artifact_ids": [
                        value.artifact_id for value in self.artifacts
                    ],
                    "producer_id": self.producer_id.value,
                    "producer_version": self.producer_version,
                },
            ),
        )

    def identity_material(self) -> dict[str, object]:
        """Return ephemeral canonical lineage material for owner identities."""
        return {
            "source_object_id": self.source_object_id.value,
            "page_location_id": self.page_location.location_id.value,
            "source_labels": self.source_labels.identity_material(),
            "source_spans": self.source_spans.identity_material(),
            "warning_ids": self.warning_ids.identity_material(),
            "artifact_ids": [value.artifact_id for value in self.artifacts],
            "producer_id": self.producer_id.value,
            "producer_version": self.producer_version,
        }
