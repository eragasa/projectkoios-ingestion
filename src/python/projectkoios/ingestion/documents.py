from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.models import ExtractionResult, Metadata
from projectkoios.ingestion.structure import StructureAnalysis


def _validate_structure_source(
    extraction: ExtractionResult,
    structure: StructureAnalysis,
) -> None:
    source = extraction.document.source
    for node in structure.nodes:
        if any(
            span.source_id != source.source_id
            or span.source_blob_id != source.blob_id
            for span in node.source_spans
        ):
            raise ValueError(
                "structure spans must refer to the exact extracted source"
            )


@dataclass(frozen=True)
class ExtractedArticle:
    extraction: ExtractionResult
    structure: StructureAnalysis
    bibliographic_candidates: Metadata = ()

    def __post_init__(self) -> None:
        _validate_structure_source(self.extraction, self.structure)


@dataclass(frozen=True)
class ExtractedTextbook:
    extraction: ExtractionResult
    structure: StructureAnalysis
    bibliographic_candidates: Metadata = ()

    def __post_init__(self) -> None:
        _validate_structure_source(self.extraction, self.structure)
