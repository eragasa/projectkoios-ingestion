"""Deterministic fixtures for current reading-evidence storage tests."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.projector.request import ProjectionRequest
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceStorageProjectionConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.projector import (  # noqa: E501
    ReadingEvidenceStorageProjector,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.read.model import (  # noqa: E501
    ReadingEvidenceReadModel,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.source import (  # noqa: E501
    ReadingEvidenceStorageProjectionSource,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.actionizer import (  # noqa: E501
    ReadingEvidenceProjectionActionizer,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.result import (  # noqa: E501
    ReadingEvidenceProjectionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)

from tests.projectkoios.ingestion.transcript.reading.evidence.projection.fixture import (  # noqa: E501
    ReadingEvidenceProjectionFixture,
)
from tests.projectkoios.ingestion.transcript.reading.evidence.projection.visual_fixture import (  # noqa: E501
    ReadingVisualProjectionFixture,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceStorageFixture:
    """Own one canonical result and its deterministic storage read model."""

    canonical: ReadingEvidenceProjectionResult
    read_model: ReadingEvidenceReadModel
    generation_id: str = "unit-test-generation"

    @classmethod
    def paragraph(cls) -> ReadingEvidenceStorageFixture:
        """Build the smallest complete paragraph-only storage fixture."""
        source = ReadingEvidenceProjectionFixture.build()
        canonical = ReadingEvidenceProjectionActionizer().action(
            request=source.request
        )
        return cls._build(canonical=canonical)

    @classmethod
    def visual(cls) -> ReadingEvidenceStorageFixture:
        """Build a complete fixture containing retained visual evidence."""
        source = ReadingVisualProjectionFixture.build()
        canonical = ReadingEvidenceProjectionActionizer().action(
            request=source.request
        )
        return cls._build(canonical=canonical)

    @classmethod
    def _build(
        cls,
        *,
        canonical: ReadingEvidenceProjectionResult,
    ) -> ReadingEvidenceStorageFixture:
        generation_id = "unit-test-generation"
        source = ReadingEvidenceStorageProjectionSource(result=canonical)
        configuration = ReadingEvidenceStorageProjectionConfiguration.v1(
            generation_id=generation_id
        )
        request = ProjectionRequest.create(
            sources=(source,),
            configuration=configuration,
        )
        result = ReadingEvidenceStorageProjector().action(request=request)
        return cls(
            canonical=canonical,
            read_model=result.projection,
            generation_id=generation_id,
        )

    def source_request(
        self,
        *,
        provider_source_id: str = "reading-evidence-test-source",
    ) -> ReadingEvidenceSourceRequest:
        """Return a bounded request for the fixture's exact canonical value."""
        return ReadingEvidenceSourceRequest(
            provider_source_id=provider_source_id,
            document_id=self.canonical.document.document_id,
            projection_result_id=self.canonical.result_id,
            inventory_id=self.canonical.inventory.inventory_id,
            maximum_page_count=10,
            maximum_block_count=100,
            maximum_artifact_count=100,
            maximum_provider_record_count=1_000,
            authority_id="unit-test-read-authority",
        )
