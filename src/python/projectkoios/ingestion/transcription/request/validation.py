from __future__ import annotations

import math
from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.equations.detection import (
    EquationDetectionResult,
)
from projectkoios.ingestion.figures import (
    EmbeddedFigureArtifact,
    FigureDetectionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
)
from projectkoios.ingestion.pdf.models import RenderedRegion
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
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.limit_error import (
    TranscriptionLimitError,
)


@dataclass(frozen=True)
class TranscriptionRequestValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    document_id: str
    validated_block_count: int
    validated_node_count: int
    validated_typed_object_count: int
    validated_artifact_bytes: int
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        document: ExtractedDocument,
        structure_analysis: StructureAnalysis,
        equation_detection_result: EquationDetectionResult,
        table_structure_result: TableStructureResult,
        figure_detection_result: FigureDetectionResult,
        configuration: TranscriptionConfiguration,
    ) -> TranscriptionRequestValidation:
        cls._validate_input_parts(
            document,
            structure_analysis,
            equation_detection_result,
            table_structure_result,
            figure_detection_result,
            configuration,
        )
        table_detection = (
            table_structure_result.structure_input.detection_result
        )
        return cls(
            document_id=document.document_id,
            validated_block_count=sum(
                len(page.blocks) for page in document.pages
            ),
            validated_node_count=len(structure_analysis.nodes),
            validated_typed_object_count=(
                len(equation_detection_result.candidates)
                + len(table_detection.candidates)
                + len(table_structure_result.structures)
                + len(figure_detection_result.candidates)
            ),
            validated_artifact_bytes=cls._input_artifact_bytes(
                equation_detection_result,
                table_structure_result,
                figure_detection_result,
            ),
        )

    @staticmethod
    def _validate_input_parts(
        document: ExtractedDocument,
        structure_analysis: StructureAnalysis,
        equation_detection_result: EquationDetectionResult,
        table_structure_result: TableStructureResult,
        figure_detection_result: FigureDetectionResult,
        configuration: TranscriptionConfiguration,
    ) -> None:
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
            AbstractTranscriptionDataObject._unit_float(
                "page extraction quality", page.extraction_quality
            )
            for block in page.blocks:
                if (
                    block.block_id
                    != TranscriptionRequestValidation._expected_block_id(block)
                ):
                    raise ValueError("document block identity is stale")
                AbstractTranscriptionDataObject._unit_float(
                    "block confidence", block.confidence
                )
                AbstractTranscriptionDataObject._validate_exact_source_spans(
                    block.source_spans, document
                )
                if block.text is not None:
                    AbstractTranscriptionDataObject._bounded_string(
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
            AbstractTranscriptionDataObject._validate_exact_source_spans(
                node.source_spans, document
            )
        for equation_candidate in equation_detection_result.candidates:
            if equation_candidate.source_block_id not in block_ids:
                raise ValueError("equation candidate source block is stale")
            AbstractTranscriptionDataObject._validate_exact_source_spans(
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
            table_block_ids, table_spans = (
                TranscriptionDerivation._table_projection(
                    structure, table_candidate
                )
            )
            if not set(table_block_ids).issubset(block_ids):
                raise ValueError("table structure source blocks are stale")
            AbstractTranscriptionDataObject._validate_exact_source_spans(
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
            AbstractTranscriptionDataObject._validate_exact_source_spans(
                figure_candidate.source_spans, document
            )
        artifact_bytes = TranscriptionRequestValidation._input_artifact_bytes(
            equation_detection_result,
            table_structure_result,
            figure_detection_result,
        )
        if artifact_bytes > configuration.max_input_artifact_bytes:
            raise TranscriptionLimitError(
                "input artifacts exceed max_input_artifact_bytes"
            )
        AbstractTranscriptionDataObject._validate_retained_size(
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

    @staticmethod
    def _expected_block_id(block: ExtractedBlock) -> str:
        has_source_local_evidence = any(
            span.source_object_id is not None
            or span.bounding_box is not None
            or span.start_offset is not None
            for span in block.source_spans
        )
        fallback_payload = (
            None
            if has_source_local_evidence
            else (block.text, block.asset_id, block.asset_mask_id)
        )
        return stable_id(
            "block",
            block.kind,
            tuple(span.identity_parts() for span in block.source_spans),
            fallback_payload,
        )

    @staticmethod
    def _input_artifact_bytes(
        equation_result: EquationDetectionResult,
        table_result: TableStructureResult,
        figure_result: FigureDetectionResult,
    ) -> int:
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
        return sum(region.byte_length for region in rendered.values()) + sum(
            artifact.byte_length + (artifact.mask_byte_length or 0)
            for artifact in embedded.values()
        )
