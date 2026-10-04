from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.equations.detection import (
    EquationDetectionResult,
)
from projectkoios.ingestion.figures import (
    FigureDetectionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import ExtractedDocument
from projectkoios.ingestion.structure import (
    StructureAnalysis,
)
from projectkoios.ingestion.tables.structure.result import TableStructureResult
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.configuration.configuration import (  # noqa: E501
    TranscriptionConfiguration,
)
from projectkoios.ingestion.transcription.configuration.error import (
    TranscriptionLimitError,
)
from projectkoios.ingestion.transcription.derivation.table import (
    TableTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.request.artifact_inventory import (
    TranscriptionInputArtifactInventory,
)
from projectkoios.ingestion.transcription.request.block_validation import (
    TranscriptionBlockValidation,
)


@dataclass(frozen=True)
class TranscriptionRequestValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    document: ExtractedDocument
    structure_analysis: StructureAnalysis
    equation_detection_result: EquationDetectionResult
    table_structure_result: TableStructureResult
    figure_detection_result: FigureDetectionResult
    configuration: TranscriptionConfiguration
    artifact_inventory: TranscriptionInputArtifactInventory
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def validate(
        cls,
        document: ExtractedDocument,
        structure_analysis: StructureAnalysis,
        equation_detection_result: EquationDetectionResult,
        table_structure_result: TableStructureResult,
        figure_detection_result: FigureDetectionResult,
        configuration: TranscriptionConfiguration,
    ) -> TranscriptionRequestValidation:
        return cls(
            document=document,
            structure_analysis=structure_analysis,
            equation_detection_result=equation_detection_result,
            table_structure_result=table_structure_result,
            figure_detection_result=figure_detection_result,
            configuration=configuration,
            artifact_inventory=TranscriptionInputArtifactInventory.derive(
                equation_detection_result,
                table_structure_result,
                figure_detection_result,
            ),
        )

    @property
    def validated_block_count(self) -> int:
        return sum(len(page.blocks) for page in self.document.pages)

    @property
    def validated_node_count(self) -> int:
        return len(self.structure_analysis.nodes)

    @property
    def validated_typed_object_count(self) -> int:
        return (
            len(self.equation_detection_result.candidates)
            + len(
                self.table_structure_result.structure_input.detection_result.candidates
            )
            + len(self.table_structure_result.structures)
            + len(self.figure_detection_result.candidates)
        )

    @property
    def validated_artifact_bytes(self) -> int:
        return self.artifact_inventory.total_bytes

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription request validation version"
            )
        document = self.document
        structure_analysis = self.structure_analysis
        equation_detection_result = self.equation_detection_result
        table_structure_result = self.table_structure_result
        figure_detection_result = self.figure_detection_result
        configuration = self.configuration
        artifact_inventory = self.artifact_inventory
        expected_artifact_inventory = (
            TranscriptionInputArtifactInventory.derive(
                equation_detection_result,
                table_structure_result,
                figure_detection_result,
            )
        )
        if artifact_inventory != expected_artifact_inventory:
            raise ValueError("input artifact inventory is inconsistent")
        if not isinstance(document, ExtractedDocument):
            raise TypeError("document must be ExtractedDocument")
        if document.document_id != stable_id(
            "document", document.source.source_id
        ):
            raise ValueError("transcription document identity is stale")
        if not isinstance(structure_analysis, StructureAnalysis):
            raise TypeError("structure_analysis must be StructureAnalysis")
        if structure_analysis.analysis_id is None or (
            structure_analysis.source_id != document.source.source_id
            or structure_analysis.source_blob_id != document.source.blob_id
        ):
            raise ValueError(
                "structure analysis must refer to the exact document"
            )
        if not isinstance(equation_detection_result, EquationDetectionResult):
            raise TypeError("equation result must be EquationDetectionResult")
        if equation_detection_result.detection_input.document != document:
            raise ValueError("equation result must retain the exact document")
        if not isinstance(table_structure_result, TableStructureResult):
            raise TypeError("table result must be TableStructureResult")
        table_detection = (
            table_structure_result.structure_input.detection_result
        )
        table_document = table_detection.detection_input.document
        if table_document != document:
            raise ValueError("table result must retain the exact document")
        if not isinstance(figure_detection_result, FigureDetectionResult):
            raise TypeError("figure result must be FigureDetectionResult")
        if figure_detection_result.detection_input.document != document:
            raise ValueError("figure result must retain the exact document")
        if not isinstance(configuration, TranscriptionConfiguration):
            raise TypeError("configuration must be TranscriptionConfiguration")
        for page in document.pages:
            if not math.isfinite(page.width) or not math.isfinite(page.height):
                raise ValueError("document page dimensions must be finite")
            AbstractTranscriptionDataObject.validate_unit_float(
                "page extraction quality", page.extraction_quality
            )
            for block in page.blocks:
                TranscriptionBlockValidation(block)
                AbstractTranscriptionDataObject.validate_unit_float(
                    "block confidence", block.confidence
                )
                AbstractTranscriptionDataObject.validate_exact_source_spans(
                    block.source_spans, document
                )
                if block.text is not None:
                    AbstractTranscriptionDataObject.validate_bounded_string(
                        "source text",
                        block.text,
                        limit=configuration.max_text_characters_per_item,
                    )
        blocks = tuple(
            block for page in document.pages for block in page.blocks
        )
        typed_count = (
            len(equation_detection_result.candidates)
            + len(table_detection.candidates)
            + len(table_structure_result.structures)
            + len(figure_detection_result.candidates)
        )
        if len(blocks) > configuration.max_input_blocks:
            raise TranscriptionLimitError(
                "input blocks exceed max_input_blocks"
            )
        if len(structure_analysis.nodes) > configuration.max_input_nodes:
            raise TranscriptionLimitError("input nodes exceed max_input_nodes")
        if typed_count > configuration.max_typed_objects:
            raise TranscriptionLimitError(
                "typed objects exceed max_typed_objects"
            )
        block_ids = {block.block_id for block in blocks}
        if len(block_ids) != len(blocks):
            raise ValueError("document block IDs must be globally unique")
        text_lengths = tuple(
            len(block.text) for block in blocks if block.text is not None
        )
        if any(
            length > configuration.max_text_characters_per_item
            for length in text_lengths
        ):
            raise TranscriptionLimitError(
                "source text exceeds max_text_characters_per_item"
            )
        if sum(text_lengths) > configuration.max_total_text_characters:
            raise TranscriptionLimitError(
                "source text exceeds max_total_text_characters"
            )
        if structure_analysis.input_block_ids != tuple(
            block.block_id for block in blocks
        ):
            raise ValueError("structure analysis input blocks are incomplete")
        for node in structure_analysis.nodes:
            if not set(node.source_block_ids).issubset(block_ids):
                raise ValueError("structure node source blocks are stale")
            AbstractTranscriptionDataObject.validate_exact_source_spans(
                node.source_spans, document
            )
        for equation_candidate in equation_detection_result.candidates:
            if equation_candidate.source_block_id not in block_ids:
                raise ValueError("equation candidate source block is stale")
            AbstractTranscriptionDataObject.validate_exact_source_spans(
                equation_candidate.source_spans, document
            )
        table_candidate_by_id = {
            candidate.candidate_id: candidate
            for candidate in table_detection.candidates
        }
        for structure in table_structure_result.structures:
            table_candidate = table_candidate_by_id.get(structure.candidate_id)
            if table_candidate is None:
                raise ValueError("table structure candidate is stale")
            page_index = min(
                region.page_index for region in table_candidate.regions
            )
            table_derivation = TableTranscriptionDerivation.derive(
                structure,
                table_candidate,
                {
                    page.page_index: page.printed_page_label
                    for page in document.pages
                }[page_index],
            )
            table_block_ids = table_derivation.source_block_ids
            table_spans = table_derivation.source_spans
            if not set(table_block_ids).issubset(block_ids):
                raise ValueError("table structure source blocks are stale")
            AbstractTranscriptionDataObject.validate_exact_source_spans(
                table_spans, document
            )
        for figure_candidate in figure_detection_result.candidates:
            candidate_blocks = {
                block_id
                for component in figure_candidate.components
                for block_id in component.source_block_ids
            } | {
                association.block_id
                for association in figure_candidate.associations
            }
            if not candidate_blocks.issubset(block_ids):
                raise ValueError("figure candidate source blocks are stale")
            AbstractTranscriptionDataObject.validate_exact_source_spans(
                figure_candidate.source_spans, document
            )
        artifact_bytes = artifact_inventory.total_bytes
        if artifact_bytes > configuration.max_input_artifact_bytes:
            raise TranscriptionLimitError(
                "input artifacts exceed max_input_artifact_bytes"
            )
        AbstractTranscriptionDataObject.validate_retained_size(
            (
                document,
                structure_analysis,
                equation_detection_result,
                table_structure_result,
                figure_detection_result,
                configuration,
            ),
            configuration.max_result_bytes,
        )
