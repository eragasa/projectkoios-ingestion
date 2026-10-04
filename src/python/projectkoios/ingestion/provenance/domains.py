"""Domain-specific transitive provenance audit walkers."""

from __future__ import annotations

import hashlib
import unicodedata
from collections import Counter
from typing import TYPE_CHECKING, Any

from projectkoios.ingestion.clean_transcript import (
    ClassificationDisposition,
    CleanTranscriptExclusionReason,
    PageNumberOutcome,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    Metadata,
    SourceDocument,
)
from projectkoios.ingestion.provenance.audit import (
    DerivationAuditFindingCode,
    DerivationAuditInput,
    _Registry,
)
from projectkoios.ingestion.transcription.source_object_kind import (
    TranscriptionSourceObjectKind,
)


class _DomainAuditWalker:
    if TYPE_CHECKING:
        audit_input: DerivationAuditInput
        extraction: ExtractionResult
        document: ExtractedDocument
        source: SourceDocument
        pages: dict[int, ExtractedPage]
        blocks: dict[str, ExtractedBlock]
        block_pages: dict[str, ExtractedPage]
        registry: _Registry

        def _add(
            self,
            code: DerivationAuditFindingCode,
            path: str,
            message: str,
            object_id: str | None = None,
            evidence: Metadata = (),
        ) -> None: ...

        def _orphan(self, path: str, object_id: str) -> None: ...

        def _require_root_document(
            self, document: ExtractedDocument, path: str
        ) -> None: ...

        def _require_registered(
            self,
            artifact: object,
            registry: dict[str, Any],
            identity: str,
            path: str,
        ) -> None: ...

    def _audit_source_content(self) -> None:
        content = self.audit_input.source_content
        digest = hashlib.sha256(content).hexdigest()
        if (
            digest != self.source.content_hash
            or len(content) != self.source.byte_length
        ):
            self._add(
                DerivationAuditFindingCode.SOURCE_CONTENT_MISMATCH,
                "source_content",
                "source bytes do not match the extraction source identity",
                self.source.source_id,
                (
                    ("actual_byte_length", str(len(content))),
                    ("actual_sha256", digest),
                    ("expected_byte_length", str(self.source.byte_length)),
                    ("expected_sha256", self.source.content_hash),
                ),
            )

    def _audit_extraction(self) -> None:
        manifest = self.extraction.manifest
        expected_objects = {self.document.document_id, *self.blocks}
        missing = expected_objects - set(manifest.object_ids)
        for object_id in sorted(missing):
            self._add(
                DerivationAuditFindingCode.ORPHAN_OBJECT_REFERENCE,
                "extraction_result.manifest.object_ids",
                "raw extraction object is absent from the manifest",
                object_id,
            )
        if len(self.blocks) != sum(
            len(page.blocks) for page in self.document.pages
        ):
            self._add(
                DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                "extraction_result.document.pages",
                "raw block IDs are not globally unique",
                self.document.document_id,
            )

    def _audit_layout_references(self) -> None:
        for result_index, result in enumerate(self.audit_input.layout_results):
            prefix = f"layout_results[{result_index}]"
            page = self.pages.get(result.page_index)
            if page is None:
                continue
            expected_ids = tuple(block.block_id for block in page.blocks)
            if result.raw_block_ids != expected_ids:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.raw_block_ids",
                    "layout raw block order differs from the root page",
                    result.result_id,
                )
            root_blocks = {block.block_id: block for block in page.blocks}
            for reference_index, reference in enumerate(result.raw_blocks):
                block = root_blocks.get(reference.block_id)
                if block is None:
                    continue
                if (
                    reference.kind != block.kind
                    or reference.source_spans != block.source_spans
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{prefix}.raw_blocks[{reference_index}]",
                        "layout block reference differs from its root block",
                        reference.block_id,
                    )

    def _audit_registered_upstreams(self) -> None:
        for index, result in enumerate(self.audit_input.reconciliation_results):
            prefix = f"reconciliation_results[{index}].reconciliation_input"
            self._require_registered(
                result.reconciliation_input.ocr_result,
                self.registry.ocr_results,
                result.reconciliation_input.ocr_result.result_id,
                f"{prefix}.ocr_result",
            )
            native_page = result.reconciliation_input.native_page
            if native_page is not None:
                root_page = self.pages.get(native_page.page_index)
                if root_page != native_page:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{prefix}.native_page",
                        "OCR reconciliation native page differs from "
                        "the root page",
                    )
            layout = result.reconciliation_input.layout_result
            if layout is not None:
                self._require_registered(
                    layout,
                    self.registry.layouts,
                    layout.result_id,
                    f"{prefix}.layout_result",
                )
        for name, results in (
            ("equation_results", self.audit_input.equation_results),
            (
                "table_detection_results",
                self.audit_input.table_detection_results,
            ),
            ("figure_results", self.audit_input.figure_results),
        ):
            for index, detection_result in enumerate(results):
                detection_value: Any = detection_result
                detection_input = detection_value.detection_input
                self._require_root_document(
                    detection_input.document,
                    f"{name}[{index}].detection_input.document",
                )
                for layout_index, layout in enumerate(detection_input.layouts):
                    self._require_registered(
                        layout,
                        self.registry.layouts,
                        layout.result_id,
                        f"{name}[{index}].detection_input.layouts[{layout_index}]",
                    )
        for index, table_structure_result in enumerate(
            self.audit_input.table_structure_results
        ):
            detection = table_structure_result.structure_input.detection_result
            self._require_registered(
                detection,
                self.registry.table_detections,
                detection.result_id,
                f"table_structure_results[{index}].structure_input.detection_result",
            )
        for index, transcription_result in enumerate(
            self.audit_input.transcription_results
        ):
            transcription_input = transcription_result.transcription_input
            prefix = f"transcription_results[{index}].transcription_input"
            self._require_root_document(
                transcription_input.document, f"{prefix}.document"
            )
            dependencies = (
                (
                    transcription_input.structure_analysis,
                    self.registry.structures,
                    transcription_input.structure_analysis.analysis_id,
                    "structure_analysis",
                ),
                (
                    transcription_input.equation_detection_result,
                    self.registry.equations,
                    transcription_input.equation_detection_result.result_id,
                    "equation_detection_result",
                ),
                (
                    transcription_input.table_structure_result,
                    self.registry.table_structures,
                    transcription_input.table_structure_result.result_id,
                    "table_structure_result",
                ),
                (
                    transcription_input.figure_detection_result,
                    self.registry.figures,
                    transcription_input.figure_detection_result.result_id,
                    "figure_detection_result",
                ),
            )
            for artifact, registry, identity, suffix in dependencies:
                if identity is None:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.{suffix}",
                        "transcription dependency has no artifact identity",
                    )
                else:
                    self._require_registered(
                        artifact,
                        registry,
                        identity,
                        f"{prefix}.{suffix}",
                    )
        for index, clean_transcript in enumerate(
            self.audit_input.clean_transcripts
        ):
            prefix = f"clean_transcripts[{index}]"
            if (
                clean_transcript.transcription_result_id
                not in self.registry.transcriptions
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                    f"{prefix}.transcription_result_id",
                    "clean transcript references an unregistered transcription",
                    clean_transcript.transcription_result_id,
                )
            for layout_index, layout_id in enumerate(
                clean_transcript.layout_result_ids
            ):
                if layout_id not in self.registry.layouts:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.layout_result_ids[{layout_index}]",
                        "clean transcript references an unregistered layout",
                        layout_id,
                    )

    def _audit_structure_references(self) -> None:
        for index, analysis in enumerate(self.audit_input.structure_analyses):
            prefix = f"structure_analyses[{index}]"
            for layout_id in analysis.layout_result_ids:
                if layout_id not in self.registry.layouts:
                    self._orphan(f"{prefix}.layout_result_ids", layout_id)
            node_ids = {node.node_id for node in analysis.nodes}
            for node_index, node in enumerate(analysis.nodes):
                node_path = f"{prefix}.nodes[{node_index}]"
                if (
                    node.parent_id is not None
                    and node.parent_id not in node_ids
                ):
                    self._orphan(f"{node_path}.parent_id", node.parent_id)
                for child_id in node.child_ids:
                    if child_id not in node_ids:
                        self._orphan(f"{node_path}.child_ids", child_id)

    def _audit_ocr_references(self) -> None:
        for result_index, result in enumerate(self.audit_input.ocr_results):
            prefix = f"ocr_results[{result_index}]"
            selections = {
                selection.selection_id: selection
                for selection in result.request.selections
            }
            for selection_index, selection_result in enumerate(
                result.selection_results
            ):
                path = f"{prefix}.selection_results[{selection_index}]"
                selection = selections.get(selection_result.selection_id)
                if selection is None:
                    self._orphan(
                        f"{path}.selection_id",
                        selection_result.selection_id,
                    )
                    continue
                if selection_result.image_id != selection.image.image_id:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{path}.image_id",
                        "OCR output image does not match its request selection",
                        selection_result.image_id,
                    )

    def _audit_reconciliation_references(self) -> None:
        for result_index, result in enumerate(
            self.audit_input.reconciliation_results
        ):
            prefix = f"reconciliation_results[{result_index}]"
            native_evidence_ids = {
                item.evidence_id for item in result.native_stream
            }
            native_segment_ids = {
                item.segment_id for item in result.native_segments
            }
            ocr_line_ids = {item.line_id for item in result.ocr_stream}
            for segment_index, segment in enumerate(result.native_segments):
                if segment.block_evidence_id not in native_evidence_ids:
                    self._orphan(
                        f"{prefix}.native_segments[{segment_index}].block_evidence_id",
                        segment.block_evidence_id,
                    )
            for match_index, match in enumerate(result.matches):
                if match.native_segment_id not in native_segment_ids:
                    self._orphan(
                        f"{prefix}.matches[{match_index}].native_segment_id",
                        match.native_segment_id,
                    )
                if match.ocr_line_id not in ocr_line_ids:
                    self._orphan(
                        f"{prefix}.matches[{match_index}].ocr_line_id",
                        match.ocr_line_id,
                    )
            for item_index, item in enumerate(result.proposed_merged_stream):
                path = f"{prefix}.proposed_merged_stream[{item_index}]"
                if (
                    item.native_segment_id is not None
                    and item.native_segment_id not in native_segment_ids
                ):
                    self._orphan(
                        f"{path}.native_segment_id", item.native_segment_id
                    )
                if (
                    item.ocr_line_id is not None
                    and item.ocr_line_id not in ocr_line_ids
                ):
                    self._orphan(f"{path}.ocr_line_id", item.ocr_line_id)

    def _audit_equation_references(self) -> None:
        for result_index, result in enumerate(
            self.audit_input.equation_results
        ):
            for candidate_index, candidate in enumerate(result.candidates):
                prefix = (
                    f"equation_results[{result_index}].candidates"
                    f"[{candidate_index}]"
                )
                for context_name in (
                    "preceding_context",
                    "following_context",
                ):
                    context = getattr(candidate, context_name)
                    if (
                        context is not None
                        and context.block_id not in self.blocks
                    ):
                        self._orphan(
                            f"{prefix}.{context_name}.block_id",
                            context.block_id,
                        )

    def _audit_table_references(self) -> None:
        candidate_by_id = {
            candidate.candidate_id: candidate
            for result in self.audit_input.table_detection_results
            for candidate in result.candidates
        }
        region_ids = {
            region.region_evidence_id
            for candidate in candidate_by_id.values()
            for region in candidate.regions
        }
        rendered_region_ids = {
            region.rendered_region.region_id
            for candidate in candidate_by_id.values()
            for region in candidate.regions
        }
        association_ids = {
            association.association_id
            for candidate in candidate_by_id.values()
            for association in candidate.associations
        }
        for result_index, result in enumerate(
            self.audit_input.table_structure_results
        ):
            for structure_index, structure in enumerate(result.structures):
                prefix = (
                    f"table_structure_results[{result_index}].structures"
                    f"[{structure_index}]"
                )
                if structure.candidate_id not in candidate_by_id:
                    self._orphan(
                        f"{prefix}.candidate_id", structure.candidate_id
                    )
                for association_id in structure.association_ids:
                    if association_id not in association_ids:
                        self._orphan(
                            f"{prefix}.association_ids", association_id
                        )
                row_ids = {row.row_id for row in structure.rows}
                column_indexes = {
                    column.column_index for column in structure.columns
                }
                for column_index, column in enumerate(structure.columns):
                    for region_id in column.source_region_ids:
                        if region_id not in region_ids:
                            self._orphan(
                                f"{prefix}.columns[{column_index}].source_region_ids",
                                region_id,
                            )
                for row_index, row in enumerate(structure.rows):
                    if row.region_id not in region_ids:
                        self._orphan(
                            f"{prefix}.rows[{row_index}].region_id",
                            row.region_id,
                        )
                for cell_index, cell in enumerate(structure.cells):
                    if cell.row_id not in row_ids:
                        self._orphan(
                            f"{prefix}.cells[{cell_index}].row_id",
                            cell.row_id,
                        )
                    if cell.column_index not in column_indexes:
                        self._orphan(
                            f"{prefix}.cells[{cell_index}].column_index",
                            str(cell.column_index),
                        )
                    for region_id in cell.rendered_region_ids:
                        if region_id not in rendered_region_ids:
                            self._orphan(
                                f"{prefix}.cells[{cell_index}].rendered_region_ids",
                                region_id,
                            )
                for continuation_index, continuation in enumerate(
                    structure.continuations
                ):
                    path = f"{prefix}.continuations[{continuation_index}]"
                    for name in ("previous_region_id", "current_region_id"):
                        value = getattr(continuation, name)
                        if value not in region_ids:
                            self._orphan(f"{path}.{name}", value)
                    if continuation.association_id not in association_ids:
                        self._orphan(
                            f"{path}.association_id",
                            continuation.association_id,
                        )

    def _audit_figure_references(self) -> None:
        for result_index, result in enumerate(self.audit_input.figure_results):
            artifact_ids = {
                artifact.artifact_id
                for evidence in result.detection_input.page_evidence
                for artifact in evidence.embedded_artifacts
            }
            drawing_ids = {
                drawing.drawing_id
                for evidence in result.detection_input.page_evidence
                for drawing in evidence.drawings
            }
            for candidate_index, candidate in enumerate(result.candidates):
                prefix = (
                    f"figure_results[{result_index}].candidates"
                    f"[{candidate_index}]"
                )
                component_ids = {
                    component.component_id for component in candidate.components
                }
                for component_index, component in enumerate(
                    candidate.components
                ):
                    path = f"{prefix}.components[{component_index}]"
                    if (
                        component.embedded_artifact_id is not None
                        and component.embedded_artifact_id not in artifact_ids
                    ):
                        self._orphan(
                            f"{path}.embedded_artifact_id",
                            component.embedded_artifact_id,
                        )
                    for drawing_id in component.drawing_evidence_ids:
                        if drawing_id not in drawing_ids:
                            self._orphan(
                                f"{path}.drawing_evidence_ids", drawing_id
                            )
                for association_index, association in enumerate(
                    candidate.associations
                ):
                    if (
                        association.component_id is not None
                        and association.component_id not in component_ids
                    ):
                        self._orphan(
                            f"{prefix}.associations[{association_index}].component_id",
                            association.component_id,
                        )

    def _audit_processing_references(self) -> None:
        for result_index, result in enumerate(
            self.audit_input.processing_results
        ):
            prefix = f"processing_results[{result_index}]"
            selection_by_id = {
                selection.selection_id: selection
                for selection in result.request.selections
            }
            work_item_by_id = {
                work_item.work_item_id: work_item
                for work_item in result.request.work_items
            }
            for selection_index, selection in enumerate(
                result.request.selections
            ):
                self._require_root_document(
                    selection.document,
                    f"{prefix}.request.selections[{selection_index}].document",
                )
                if selection.structure_analysis is not None:
                    identity = selection.structure_analysis.analysis_id
                    if identity is None:
                        self._add(
                            DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                            f"{prefix}.request.selections[{selection_index}].structure_analysis",
                            "processing selection structure has no identity",
                        )
                    else:
                        self._require_registered(
                            selection.structure_analysis,
                            self.registry.structures,
                            identity,
                            f"{prefix}.request.selections[{selection_index}].structure_analysis",
                        )
            for work_index, work_item in enumerate(result.request.work_items):
                path = f"{prefix}.request.work_items[{work_index}]"
                if work_item.source != self.source:
                    self._add(
                        DerivationAuditFindingCode.SOURCE_DOCUMENT_MISMATCH,
                        f"{path}.source",
                        "processing work item source differs from root source",
                        work_item.work_item_id,
                    )
                for page_index, full_page in enumerate(work_item.full_pages):
                    root_page = self.pages.get(full_page.page_index)
                    if root_page != full_page:
                        self._add(
                            DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                            f"{path}.full_pages[{page_index}]",
                            "processing work item page differs from "
                            "the root page",
                            work_item.work_item_id,
                        )
            for selection_result_index, selection_result in enumerate(
                result.selection_results
            ):
                path = f"{prefix}.selection_results[{selection_result_index}]"
                if selection_result.selection_id not in selection_by_id:
                    self._orphan(
                        f"{path}.selection_id",
                        selection_result.selection_id,
                    )
                registered_work_item = work_item_by_id.get(
                    selection_result.work_item.work_item_id
                )
                if registered_work_item is None:
                    self._orphan(
                        f"{path}.work_item.work_item_id",
                        selection_result.work_item.work_item_id,
                    )
                elif registered_work_item != selection_result.work_item:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{path}.work_item",
                        "processing selection result embeds different "
                        "work item evidence",
                        selection_result.work_item.work_item_id,
                    )
                allowed_input_ids = set(
                    selection_result.work_item.input_object_ids
                )
                for attempt_index, attempt in enumerate(
                    selection_result.attempts
                ):
                    invocation = attempt.invocation
                    for artifact_index, artifact in enumerate(
                        invocation.artifacts
                    ):
                        for object_id in artifact.input_object_ids:
                            if object_id not in allowed_input_ids:
                                self._orphan(
                                    f"{path}.attempts[{attempt_index}].invocation.artifacts"
                                    f"[{artifact_index}].input_object_ids",
                                    object_id,
                                )

    def _audit_transcription_references(self) -> None:
        structure_ids = {
            node.node_id
            for analysis in self.audit_input.structure_analyses
            for node in analysis.nodes
        }
        equation_ids = {
            candidate.candidate_id
            for result in self.audit_input.equation_results
            for candidate in result.candidates
        }
        table_structure_ids = {
            structure.structure_id
            for result in self.audit_input.table_structure_results
            for structure in result.structures
        }
        figure_ids = {
            candidate.candidate_id
            for result in self.audit_input.figure_results
            for candidate in result.candidates
        }
        page_anchor_ids = {
            stable_id(
                "transcription-page-anchor",
                self.source.source_id,
                self.source.blob_id,
                page.page_index,
            )
            for page in self.document.pages
        }
        expected = {
            TranscriptionSourceObjectKind.PAGE: page_anchor_ids,
            TranscriptionSourceObjectKind.RAW_BLOCK: set(self.blocks),
            TranscriptionSourceObjectKind.STRUCTURE_NODE: structure_ids,
            TranscriptionSourceObjectKind.EQUATION_CANDIDATE: equation_ids,
            TranscriptionSourceObjectKind.TABLE_STRUCTURE: table_structure_ids,
            TranscriptionSourceObjectKind.FIGURE_CANDIDATE: figure_ids,
        }
        all_source_objects = set().union(*expected.values())
        for result_index, result in enumerate(
            self.audit_input.transcription_results
        ):
            item_ids = {item.item_id for item in result.items}
            for item_index, item in enumerate(result.items):
                if (
                    item.source_object_id
                    not in expected[item.source_object_kind]
                ):
                    self._orphan(
                        f"transcription_results[{result_index}].items"
                        f"[{item_index}].source_object_id",
                        item.source_object_id,
                    )
            for omission_index, omission in enumerate(result.omissions):
                prefix = (
                    f"transcription_results[{result_index}].omissions"
                    f"[{omission_index}]"
                )
                if omission.omitted_object_id not in all_source_objects:
                    self._orphan(
                        f"{prefix}.omitted_object_id",
                        omission.omitted_object_id,
                    )
                for item_id in omission.represented_by_item_ids:
                    if item_id not in item_ids:
                        self._orphan(
                            f"{prefix}.represented_by_item_ids", item_id
                        )

    def _audit_clean_transcript_references(self) -> None:
        root_page_indexes = tuple(
            page.page_index for page in self.document.pages
        )
        eligible_root_ids = tuple(
            block.block_id
            for page in self.document.pages
            for block in page.blocks
            if block.kind == "text" and block.text is not None
        )
        for artifact_index, artifact in enumerate(
            self.audit_input.clean_transcripts
        ):
            prefix = f"clean_transcripts[{artifact_index}]"
            if (
                artifact.document_id != self.document.document_id
                or artifact.source_id != self.source.source_id
                or artifact.source_blob_id != self.source.blob_id
                or artifact.source_content_hash != self.source.content_hash
            ):
                self._add(
                    DerivationAuditFindingCode.SOURCE_DOCUMENT_MISMATCH,
                    prefix,
                    "clean transcript differs from the root source document",
                    artifact.result_id,
                )
            included_by_block = {
                record.block_id: record for record in artifact.blocks
            }
            excluded_by_block = {
                exclusion.block_id: exclusion
                for exclusion in artifact.exclusions
            }
            coverage_counts = Counter(
                (
                    *(record.block_id for record in artifact.blocks),
                    *(item.block_id for item in artifact.exclusions),
                )
            )
            for block_id in eligible_root_ids:
                count = coverage_counts[block_id]
                if count == 0:
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        f"{prefix}.blocks_and_exclusions",
                        "eligible root block is absent from clean transcript",
                        block_id,
                    )
                elif count > 1:
                    self._add(
                        DerivationAuditFindingCode.DUPLICATE_OBJECT_ID,
                        f"{prefix}.blocks_and_exclusions",
                        "root block occurs more than once in clean transcript",
                        block_id,
                    )
            for record_index, record in enumerate(artifact.blocks):
                path = f"{prefix}.blocks[{record_index}]"
                root = self.blocks.get(record.block_id)
                root_page = self.block_pages.get(record.block_id)
                if root is None or root_page is None:
                    self._orphan(f"{path}.block_id", record.block_id)
                elif (
                    root.kind != "text"
                    or root.text is None
                    or root.text != record.raw_text
                    or root.source_spans != record.source_spans
                    or root_page.page_index != record.page_index
                    or root_page.printed_page_label != record.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "clean transcript block differs from its root block",
                        record.record_id,
                    )
            for exclusion_index, exclusion in enumerate(artifact.exclusions):
                path = f"{prefix}.exclusions[{exclusion_index}]"
                root = self.blocks.get(exclusion.block_id)
                root_page = self.block_pages.get(exclusion.block_id)
                if root is None or root_page is None:
                    self._orphan(f"{path}.block_id", exclusion.block_id)
                elif (
                    root.kind != "text"
                    or root.text is None
                    or root.text != exclusion.raw_text
                    or root.source_spans != exclusion.source_spans
                    or root_page.page_index != exclusion.page_index
                    or root_page.printed_page_label
                    != exclusion.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "clean transcript exclusion differs from its "
                        "root block",
                        exclusion.exclusion_id,
                    )
            page_classification_by_id = {
                item.classification_id: item
                for item in artifact.page_number_classifications
            }
            publisher_by_id = {
                item.classification_id: item
                for item in artifact.publisher_front_matter
            }
            exclusions_by_decision = {
                item.decision_id: item
                for item in artifact.exclusions
                if item.decision_id is not None
            }
            for decision_index, decision in enumerate(
                artifact.dehyphenation_decisions
            ):
                path = f"{prefix}.dehyphenation_decisions[{decision_index}]"
                root = self.blocks.get(decision.block_id)
                root_page = self.block_pages.get(decision.block_id)
                if root is None or root_page is None or root.text is None:
                    self._orphan(f"{path}.block_id", decision.block_id)
                elif (
                    root.source_spans != decision.source_spans
                    or root_page.page_index != decision.page_index
                    or root_page.printed_page_label
                    != decision.printed_page_label
                    or decision.end_offset > len(root.text)
                    or root.text[decision.start_offset : decision.end_offset]
                    != decision.raw_fragment
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "dehyphenation decision differs from source evidence",
                        decision.decision_id,
                    )
            for classification_index, page_classification in enumerate(
                artifact.page_number_classifications
            ):
                path = (
                    f"{prefix}.page_number_classifications"
                    f"[{classification_index}]"
                )
                root = self.blocks.get(page_classification.block_id)
                root_page = self.block_pages.get(page_classification.block_id)
                boxes = (
                    tuple(
                        span.bounding_box
                        for span in root.source_spans
                        if span.bounding_box is not None
                    )
                    if root is not None
                    else ()
                )
                expected_box = (
                    (
                        min(box[0] for box in boxes),
                        min(box[1] for box in boxes),
                        max(box[2] for box in boxes),
                        max(box[3] for box in boxes),
                    )
                    if boxes
                    else None
                )
                if root is None or root_page is None or root.text is None:
                    self._orphan(
                        f"{path}.block_id", page_classification.block_id
                    )
                elif (
                    root.text != page_classification.raw_text
                    or root.source_spans != page_classification.source_spans
                    or root_page.page_index != page_classification.page_index
                    or root_page.printed_page_label
                    != page_classification.printed_page_label
                    or page_classification.bounding_box != expected_box
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "page-number decision differs from source evidence",
                        page_classification.classification_id,
                    )
                page_exclusion = exclusions_by_decision.get(
                    page_classification.classification_id
                )
                if (
                    page_classification.outcome is PageNumberOutcome.PAGE_NUMBER
                    and (
                        page_exclusion is None
                        or page_exclusion.reason
                        is not CleanTranscriptExclusionReason.PAGE_NUMBER
                    )
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        path,
                        "page-number decision lacks its typed exclusion",
                        page_classification.classification_id,
                    )
                if (
                    page_classification.outcome
                    is not PageNumberOutcome.PAGE_NUMBER
                    and page_exclusion is not None
                    and page_exclusion.reason
                    is CleanTranscriptExclusionReason.PAGE_NUMBER
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "non-page-number evidence was excluded as a page "
                        "number",
                        page_classification.classification_id,
                    )
            for classification_index, publisher_classification in enumerate(
                artifact.publisher_front_matter
            ):
                path = (
                    f"{prefix}.publisher_front_matter[{classification_index}]"
                )
                root = self.blocks.get(publisher_classification.block_id)
                root_page = self.block_pages.get(
                    publisher_classification.block_id
                )
                if root is None or root_page is None:
                    self._orphan(
                        f"{path}.block_id",
                        publisher_classification.block_id,
                    )
                elif (
                    root.source_spans != publisher_classification.source_spans
                    or root_page.page_index
                    != publisher_classification.page_index
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "publisher classification differs from source evidence",
                        publisher_classification.classification_id,
                    )
                publisher_exclusion = exclusions_by_decision.get(
                    publisher_classification.classification_id
                )
                if (
                    publisher_classification.disposition
                    is ClassificationDisposition.EXCLUDED
                    and (
                        publisher_exclusion is None
                        or publisher_exclusion.reason
                        is not (
                            CleanTranscriptExclusionReason.PUBLISHER_FRONT_MATTER
                        )
                    )
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISSING,
                        path,
                        "publisher exclusion lacks its classification",
                        publisher_classification.classification_id,
                    )
            for finding_index, finding in enumerate(
                artifact.private_use_glyph_findings
            ):
                path = f"{prefix}.private_use_glyph_findings[{finding_index}]"
                root = self.blocks.get(finding.block_id)
                root_page = self.block_pages.get(finding.block_id)
                if root is None or root_page is None or root.text is None:
                    self._orphan(f"{path}.block_id", finding.block_id)
                elif (
                    root.source_spans != finding.source_spans
                    or root_page.page_index != finding.page_index
                    or root_page.printed_page_label
                    != finding.printed_page_label
                    or finding.character_offset >= len(root.text)
                    or root.text[finding.character_offset]
                    != finding.raw_character
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        path,
                        "private-use finding differs from source evidence",
                        finding.finding_id,
                    )
            expected_private_use = {
                (block.block_id, offset, character)
                for page in self.document.pages
                for block in page.blocks
                if block.kind == "text" and block.text is not None
                for offset, character in enumerate(block.text)
                if unicodedata.category(character) == "Co"
            }
            actual_private_use = {
                (item.block_id, item.character_offset, item.raw_character)
                for item in artifact.private_use_glyph_findings
            }
            if actual_private_use != expected_private_use:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.private_use_glyph_findings",
                    "private-use findings do not exactly cover source glyphs",
                    artifact.result_id,
                )
            actual_page_indexes = tuple(
                page.page_index for page in artifact.pages
            )
            if actual_page_indexes != root_page_indexes:
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.pages",
                    "clean transcript pages do not exactly cover root pages",
                    artifact.result_id,
                )
            layouts = tuple(
                self.registry.layouts[layout_id]
                for layout_id in artifact.layout_result_ids
                if layout_id in self.registry.layouts
            )
            layout_by_page = {layout.page_index: layout for layout in layouts}
            expected_record_ids: list[str] = []
            expected_exclusion_ids: list[str] = []
            for page_index, root_page in enumerate(self.document.pages):
                block_by_id = {
                    block.block_id: block for block in root_page.blocks
                }
                text_ids = tuple(
                    block.block_id
                    for block in root_page.blocks
                    if block.kind == "text" and block.text is not None
                )
                layout = layout_by_page.get(root_page.page_index)
                ordered_ids = (
                    tuple(
                        block_id
                        for block_id in layout.proposed_order
                        if block_id in block_by_id
                        and block_by_id[block_id].kind == "text"
                        and block_by_id[block_id].text is not None
                    )
                    if layout is not None
                    else text_ids
                )
                root_order = (
                    *ordered_ids,
                    *(
                        block_id
                        for block_id in text_ids
                        if block_id not in ordered_ids
                    ),
                )
                page_record_ids = tuple(
                    included_by_block[block_id].record_id
                    for block_id in root_order
                    if block_id in included_by_block
                )
                expected_record_ids.extend(page_record_ids)
                expected_exclusion_ids.extend(
                    excluded_by_block[block_id].exclusion_id
                    for block_id in root_order
                    if block_id in excluded_by_block
                )
                if (
                    page_index >= len(artifact.pages)
                    or artifact.pages[page_index].block_record_ids
                    != page_record_ids
                    or artifact.pages[page_index].printed_page_label
                    != root_page.printed_page_label
                ):
                    self._add(
                        DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                        f"{prefix}.pages[{page_index}]",
                        "clean transcript page membership differs from layout",
                        artifact.result_id,
                    )
            if tuple(item.record_id for item in artifact.blocks) != tuple(
                expected_record_ids
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.blocks",
                    "clean transcript blocks are not in exact layout order",
                    artifact.result_id,
                )
            if tuple(
                item.exclusion_id for item in artifact.exclusions
            ) != tuple(expected_exclusion_ids):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.exclusions",
                    "clean transcript exclusions are not in exact layout order",
                    artifact.result_id,
                )
            if tuple(item.order_index for item in artifact.blocks) != tuple(
                range(len(artifact.blocks))
            ):
                self._add(
                    DerivationAuditFindingCode.UPSTREAM_ARTIFACT_MISMATCH,
                    f"{prefix}.blocks",
                    "clean transcript retained order is not contiguous",
                    artifact.result_id,
                )
            expected_text = (
                "\n\n".join(page.text for page in artifact.pages) + "\n"
            )
            if artifact.text != expected_text:
                self._add(
                    DerivationAuditFindingCode.CONTENT_IDENTITY_MISMATCH,
                    f"{prefix}.text",
                    "clean transcript text differs from page projections",
                    artifact.result_id,
                )
            for record in artifact.blocks:
                if record.page_number_classification_id is not None and (
                    record.page_number_classification_id
                    not in page_classification_by_id
                ):
                    self._orphan(
                        f"{prefix}.blocks.page_number_classification_id",
                        record.page_number_classification_id,
                    )
                if record.publisher_classification_id is not None and (
                    record.publisher_classification_id not in publisher_by_id
                ):
                    self._orphan(
                        f"{prefix}.blocks.publisher_classification_id",
                        record.publisher_classification_id,
                    )
