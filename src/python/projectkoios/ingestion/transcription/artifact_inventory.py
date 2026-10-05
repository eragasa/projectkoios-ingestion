from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.equations.detection import EquationDetectionResult
from projectkoios.ingestion.figures import (
    EmbeddedFigureArtifact,
    FigureDetectionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.pdf.models import RenderedRegion
from projectkoios.ingestion.tables.structure.result import TableStructureResult
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)


@dataclass(frozen=True)
class TranscriptionInputArtifactInventory(
    AbstractDerivation, AbstractTranscriptionDataObject
):
    inventory_id: str
    rendered_region_ids: tuple[str, ...]
    embedded_artifact_ids: tuple[str, ...]
    rendered_bytes: int
    embedded_bytes: int
    mask_bytes: int
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
        rendered_region_ids = tuple(rendered)
        embedded_artifact_ids = tuple(embedded)
        rendered_bytes = sum(region.byte_length for region in rendered.values())
        embedded_bytes = sum(
            artifact.byte_length for artifact in embedded.values()
        )
        mask_bytes = sum(
            artifact.mask_byte_length or 0 for artifact in embedded.values()
        )
        total_bytes = rendered_bytes + embedded_bytes + mask_bytes
        identity_parts = (
            rendered_region_ids,
            embedded_artifact_ids,
            rendered_bytes,
            embedded_bytes,
            mask_bytes,
            total_bytes,
        )
        return cls(
            inventory_id=stable_id(
                "transcription-input-artifact-inventory", *identity_parts
            ),
            rendered_region_ids=rendered_region_ids,
            embedded_artifact_ids=embedded_artifact_ids,
            rendered_bytes=rendered_bytes,
            embedded_bytes=embedded_bytes,
            mask_bytes=mask_bytes,
            total_bytes=total_bytes,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported input-artifact inventory version")
        self.validate_identity_fields(self.inventory_id)
        self.validate_unique_strings(
            "rendered region IDs", self.rendered_region_ids
        )
        self.validate_unique_strings(
            "embedded artifact IDs", self.embedded_artifact_ids
        )
        for name, value in (
            ("rendered artifact bytes", self.rendered_bytes),
            ("embedded artifact bytes", self.embedded_bytes),
            ("embedded mask bytes", self.mask_bytes),
            ("input artifact bytes", self.total_bytes),
        ):
            self.validate_nonnegative_integer(name, value)
        expected_total = (
            self.rendered_bytes + self.embedded_bytes + self.mask_bytes
        )
        if self.total_bytes != expected_total:
            raise ValueError("input artifact byte total is inconsistent")
        expected_id = stable_id(
            "transcription-input-artifact-inventory",
            self.rendered_region_ids,
            self.embedded_artifact_ids,
            self.rendered_bytes,
            self.embedded_bytes,
            self.mask_bytes,
            self.total_bytes,
        )
        if self.inventory_id != expected_id:
            raise ValueError(
                "input artifact inventory identity is inconsistent"
            )
