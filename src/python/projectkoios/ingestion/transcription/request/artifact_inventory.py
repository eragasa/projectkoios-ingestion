from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.equations.detection import EquationDetectionResult
from projectkoios.ingestion.figures import (
    EmbeddedFigureArtifact,
    FigureDetectionResult,
)
from projectkoios.ingestion.pdf.models import RenderedRegion
from projectkoios.ingestion.tables.structure.result import TableStructureResult
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)


@dataclass(frozen=True)
class TranscriptionInputArtifactInventory(
    AbstractDerivation, AbstractTranscriptionDataObject
):
    rendered_regions: tuple[RenderedRegion, ...]
    embedded_artifacts: tuple[EmbeddedFigureArtifact, ...]
    total_bytes: int
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def derive(
        cls,
        equation_result: EquationDetectionResult,
        table_result: TableStructureResult,
        figure_result: FigureDetectionResult,
    ) -> TranscriptionInputArtifactInventory:
        rendered: dict[str, RenderedRegion] = {}
        embedded: dict[str, EmbeddedFigureArtifact] = {}
        for equation_candidate in equation_result.candidates:
            rendered[equation_candidate.rendered_region.region_id] = (
                equation_candidate.rendered_region
            )
        for (
            table_candidate
        ) in table_result.structure_input.detection_result.candidates:
            for region in table_candidate.regions:
                rendered[region.rendered_region.region_id] = (
                    region.rendered_region
                )
        for page in figure_result.detection_input.page_evidence:
            for artifact in page.embedded_artifacts:
                embedded[artifact.artifact_id] = artifact
        for figure_candidate in figure_result.candidates:
            for component in figure_candidate.components:
                if component.rendered_region is not None:
                    rendered[component.rendered_region.region_id] = (
                        component.rendered_region
                    )
        rendered_regions = tuple(rendered.values())
        embedded_artifacts = tuple(embedded.values())
        total_bytes = sum(
            region.byte_length for region in rendered_regions
        ) + sum(
            artifact.byte_length + (artifact.mask_byte_length or 0)
            for artifact in embedded_artifacts
        )
        return cls(rendered_regions, embedded_artifacts, total_bytes)

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported input-artifact inventory version")
        self.validate_tuple("rendered regions", self.rendered_regions)
        self.validate_tuple("embedded artifacts", self.embedded_artifacts)
        if any(
            not isinstance(value, RenderedRegion)
            for value in self.rendered_regions
        ):
            raise TypeError("artifact inventory contains an unsupported region")
        if any(
            not isinstance(value, EmbeddedFigureArtifact)
            for value in self.embedded_artifacts
        ):
            raise TypeError(
                "artifact inventory contains an unsupported artifact"
            )
        self.validate_nonnegative_integer(
            "input artifact bytes", self.total_bytes
        )
        expected = sum(
            region.byte_length for region in self.rendered_regions
        ) + sum(
            artifact.byte_length + (artifact.mask_byte_length or 0)
            for artifact in self.embedded_artifacts
        )
        if self.total_bytes != expected:
            raise ValueError("input artifact byte count is inconsistent")
