"""Semantic performer for bounded transcript evidence selection."""

from __future__ import annotations

import re
from typing import ClassVar

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    CleanTranscriptBlock,
    CleanTranscriptPage,
    CleanTranscriptStatus,
    DehyphenationOutcome,
    PageNumberOutcome,
    PublisherFrontMatterKind,
)
from projectkoios.ingestion.transcript.evidence.selection.contracts import (
    TranscriptEvidenceSelectionOutcome,
    TranscriptEvidenceSelectionRequest,
    TranscriptEvidenceSelectionResult,
)
from projectkoios.ingestion.transcript.evidence.selection.evidence import (
    SelectedTranscriptBlockEvidence,
    SelectedTranscriptPageEvidence,
    TranscriptEvidenceMappingBasis,
)


class TranscriptEvidenceSelector(
    DataObjectActionizer[
        TranscriptEvidenceSelectionRequest,
        TranscriptEvidenceSelectionResult,
    ]
):
    """Select bounded paired transcript evidence without authoring decisions."""

    __slots__ = ()

    IMPLEMENTATION_IDENTITY: ClassVar[str] = (
        "projectkoios.ingestion.transcript-evidence-selector"
    )
    _BLOCK_RECORD_ID: ClassVar[re.Pattern[str]] = re.compile(
        r"clean-transcript-block:sha256:[0-9a-f]{64}"
    )

    def action(
        self,
        *,
        request: TranscriptEvidenceSelectionRequest,
    ) -> TranscriptEvidenceSelectionResult:
        """Delegate to the only semantic evidence-selection path."""

        return self.select(request=request)

    def select(
        self,
        *,
        request: TranscriptEvidenceSelectionRequest,
    ) -> TranscriptEvidenceSelectionResult:
        """Select exact block pairs in canonical transcript order."""

        if type(request) is not TranscriptEvidenceSelectionRequest:
            raise TypeError(
                "request must be a TranscriptEvidenceSelectionRequest"
            )
        transcript = request.transcript
        selection_errors = self._selection_errors(
            request.selected_block_record_ids
        )
        duplicates = self._duplicates(request.selected_block_record_ids)
        warning_map = self._warning_block_map(transcript)
        warning_inspection_possible = all(
            block_ids is not None for block_ids in warning_map.values()
        )
        if selection_errors:
            return self._result(
                request=request,
                outcome=TranscriptEvidenceSelectionOutcome.INVALID_SELECTION,
                selection_errors=selection_errors,
                duplicates=duplicates,
                warning_inspection_possible=warning_inspection_possible,
            )
        if not self._transcript_is_complete(transcript):
            return self._result(
                request=request,
                outcome=(
                    TranscriptEvidenceSelectionOutcome.TRANSCRIPT_NOT_COMPLETE
                ),
                warning_inspection_possible=warning_inspection_possible,
            )
        block_by_record_id = {
            block.record_id: block for block in transcript.blocks
        }
        missing = tuple(
            record_id
            for record_id in request.selected_block_record_ids
            if record_id not in block_by_record_id
        )
        if missing:
            return self._result(
                request=request,
                outcome=TranscriptEvidenceSelectionOutcome.MISSING_BLOCK,
                missing=missing,
                warning_inspection_possible=warning_inspection_possible,
            )
        selected = tuple(
            block
            for block in transcript.blocks
            if block.record_id in set(request.selected_block_record_ids)
        )
        selected_block_ids = {block.block_id for block in selected}
        inspection_warnings = tuple(
            sorted(
                warning
                for warning, affected_block_ids in warning_map.items()
                if affected_block_ids is None
                or bool(selected_block_ids & affected_block_ids)
            )
        )
        if inspection_warnings:
            return self._result(
                request=request,
                outcome=(
                    TranscriptEvidenceSelectionOutcome.WARNING_INSPECTION_REQUIRED
                ),
                inspection_warnings=inspection_warnings,
                warning_inspection_possible=warning_inspection_possible,
            )
        blocks = self._block_evidence(transcript, selected)
        pages = self._page_evidence(transcript, blocks)
        return self._result(
            request=request,
            outcome=TranscriptEvidenceSelectionOutcome.EVIDENCE_AVAILABLE,
            pages=pages,
            blocks=blocks,
            warning_inspection_possible=warning_inspection_possible,
        )

    @classmethod
    def _selection_errors(cls, record_ids: tuple[str, ...]) -> tuple[str, ...]:
        errors: set[str] = set()
        if not record_ids:
            errors.add("empty_selection")
        if len(record_ids) != len(set(record_ids)):
            errors.add("duplicate_block_record_ids")
        if any(
            cls._BLOCK_RECORD_ID.fullmatch(value) is None
            for value in record_ids
        ):
            errors.add("invalid_block_record_id")
        return tuple(sorted(errors))

    @staticmethod
    def _duplicates(record_ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sorted(
                record_id
                for record_id in set(record_ids)
                if record_ids.count(record_id) > 1
            )
        )

    @classmethod
    def _transcript_is_complete(cls, transcript: CleanTranscript) -> bool:
        if transcript.status is not CleanTranscriptStatus.AUTOMATED_UNREVIEWED:
            return False
        if tuple(page.page_index for page in transcript.pages) != tuple(
            range(len(transcript.pages))
        ):
            return False
        if len({page.page_id for page in transcript.pages}) != len(
            transcript.pages
        ):
            return False
        if tuple(block.order_index for block in transcript.blocks) != tuple(
            range(len(transcript.blocks))
        ):
            return False
        page_record_ids = tuple(
            record_id
            for page in transcript.pages
            for record_id in page.block_record_ids
        )
        if page_record_ids != tuple(
            block.record_id for block in transcript.blocks
        ):
            return False
        block_by_record_id = {
            block.record_id: block for block in transcript.blocks
        }
        for page in transcript.pages:
            records: list[CleanTranscriptBlock] = []
            for record_id in page.block_record_ids:
                block = block_by_record_id.get(record_id)
                if (
                    block is None
                    or block.page_index != page.page_index
                    or block.printed_page_label != page.printed_page_label
                ):
                    return False
                records.append(block)
            if page.text != cls._expected_page_text(page, tuple(records)):
                return False
        return True

    @staticmethod
    def _expected_page_text(
        page: CleanTranscriptPage,
        records: tuple[CleanTranscriptBlock, ...],
    ) -> str:
        label = (
            "none"
            if page.printed_page_label is None
            else page.printed_page_label.replace('"', "'")
        )
        marker = f'[[PAGE physical={page.page_index + 1} printed="{label}"]]'
        body = "\n\n".join(record.clean_text for record in records)
        return marker if not body else f"{marker}\n\n{body}"

    @classmethod
    def _warning_block_map(
        cls, transcript: CleanTranscript
    ) -> dict[str, set[str] | None]:
        mapping: dict[str, set[str] | None] = {}
        for warning in transcript.warnings:
            affected: set[str] | None
            if warning == "private_use_glyph_retained":
                affected = {
                    finding.block_id
                    for finding in transcript.private_use_glyph_findings
                }
            elif warning == "ambiguous_dehyphenation_retained":
                affected = {
                    decision.block_id
                    for decision in transcript.dehyphenation_decisions
                    if decision.outcome
                    is DehyphenationOutcome.PRESERVE_BREAK_CONSERVATIVELY
                }
            elif warning == "control_characters_replaced":
                affected = cls._transformed_block_ids(
                    transcript, "control_character_offsets"
                )
            elif warning == "soft_hyphens_removed":
                affected = cls._transformed_block_ids(
                    transcript, "soft_hyphen_offsets"
                )
            elif warning == "unresolved_page_number_classification":
                affected = {
                    item.block_id
                    for item in transcript.page_number_classifications
                    if item.outcome is PageNumberOutcome.UNRESOLVED
                }
            elif warning == "unrecognized_publisher_front_matter":
                affected = {
                    item.block_id
                    for item in transcript.publisher_front_matter
                    if item.kind is PublisherFrontMatterKind.UNRECOGNIZED
                }
            else:
                affected = None
            mapping[warning] = affected
        return mapping

    @staticmethod
    def _transformed_block_ids(
        transcript: CleanTranscript, transformation_name: str
    ) -> set[str]:
        return {
            block.block_id
            for block in transcript.blocks
            if any(
                name == transformation_name and bool(value)
                for name, value in block.transformations
            )
        }

    @staticmethod
    def _block_evidence(
        transcript: CleanTranscript,
        selected: tuple[CleanTranscriptBlock, ...],
    ) -> tuple[SelectedTranscriptBlockEvidence, ...]:
        page_by_index = {page.page_index: page for page in transcript.pages}
        return tuple(
            SelectedTranscriptBlockEvidence(
                transcript_result_id=transcript.result_id,
                page_id=page_by_index[block.page_index].page_id,
                page_index=block.page_index,
                printed_page_label=block.printed_page_label,
                block_id=block.block_id,
                block_record_id=block.record_id,
                order_index=block.order_index,
                indexed_clean_text=block.clean_text,
                retained_raw_text=block.raw_text,
                mapping_basis=(
                    TranscriptEvidenceMappingBasis.CLEAN_TRANSCRIPT_BLOCK_EXACT_PAIR
                ),
                transformation_evidence=block.transformations,
                dehyphenation_decision_ids=block.dehyphenation_decision_ids,
            )
            for block in selected
        )

    @staticmethod
    def _page_evidence(
        transcript: CleanTranscript,
        blocks: tuple[SelectedTranscriptBlockEvidence, ...],
    ) -> tuple[SelectedTranscriptPageEvidence, ...]:
        pages: list[SelectedTranscriptPageEvidence] = []
        for transcript_page in transcript.pages:
            page_blocks = tuple(
                block
                for block in blocks
                if block.page_id == transcript_page.page_id
            )
            if not page_blocks:
                continue
            pages.append(
                SelectedTranscriptPageEvidence(
                    transcript_result_id=transcript.result_id,
                    page_id=transcript_page.page_id,
                    page_index=transcript_page.page_index,
                    printed_page_label=transcript_page.printed_page_label,
                    selected_block_evidence_ids=tuple(
                        block.selected_block_evidence_id
                        for block in page_blocks
                    ),
                    block_ids=tuple(block.block_id for block in page_blocks),
                    block_record_ids=tuple(
                        block.block_record_id for block in page_blocks
                    ),
                )
            )
        return tuple(pages)

    @classmethod
    def _result(
        cls,
        *,
        request: TranscriptEvidenceSelectionRequest,
        outcome: TranscriptEvidenceSelectionOutcome,
        pages: tuple[SelectedTranscriptPageEvidence, ...] = (),
        blocks: tuple[SelectedTranscriptBlockEvidence, ...] = (),
        selection_errors: tuple[str, ...] = (),
        duplicates: tuple[str, ...] = (),
        missing: tuple[str, ...] = (),
        inspection_warnings: tuple[str, ...] = (),
        warning_inspection_possible: bool,
    ) -> TranscriptEvidenceSelectionResult:
        return TranscriptEvidenceSelectionResult(
            request=request,
            transcript_result_id=request.transcript.result_id,
            selector_implementation_identity=cls.IMPLEMENTATION_IDENTITY,
            outcome=outcome,
            pages=pages,
            blocks=blocks,
            selection_errors=tuple(sorted(set(selection_errors))),
            duplicate_block_record_ids=tuple(sorted(set(duplicates))),
            missing_block_record_ids=tuple(sorted(set(missing))),
            transcript_warnings=request.transcript.warnings,
            warnings_requiring_inspection=tuple(
                sorted(set(inspection_warnings))
            ),
            block_resolved_warning_inspection_possible=(
                warning_inspection_possible
            ),
        )


__all__ = ["TranscriptEvidenceSelector"]
