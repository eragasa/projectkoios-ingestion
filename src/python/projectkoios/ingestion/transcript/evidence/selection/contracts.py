"""Immutable contracts for bounded transcript evidence selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest, DataObjectActionResult
from projectkoios.ingestion.clean_transcript import CleanTranscript
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.transcript.evidence.selection.evidence import (
    SelectedTranscriptBlockEvidence,
    SelectedTranscriptPageEvidence,
)


class TranscriptEvidenceSelectionLimitError(ValueError):
    """Raised before a transcript evidence selection exceeds a hard bound."""


class TranscriptEvidenceSelectionOutcome(StrEnum):
    """Closed outcomes for one clean-transcript evidence selection."""

    INVALID_SELECTION = "INVALID_SELECTION"
    MISSING_BLOCK = "MISSING_BLOCK"
    TRANSCRIPT_NOT_COMPLETE = "TRANSCRIPT_NOT_COMPLETE"
    WARNING_INSPECTION_REQUIRED = "WARNING_INSPECTION_REQUIRED"
    EVIDENCE_AVAILABLE = "EVIDENCE_AVAILABLE"


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriptEvidenceSelectionRequest(DataObjectActionRequest):
    """Bind one canonical transcript to a bounded block-record selection."""

    MAX_SELECTED_BLOCKS: ClassVar[int] = 256
    MAX_ID_CHARACTERS: ClassVar[int] = 512

    transcript: CleanTranscript
    selected_block_record_ids: tuple[str, ...]
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.transcript) is not CleanTranscript:
            raise TypeError("transcript must be a CleanTranscript")
        if type(self.selected_block_record_ids) is not tuple:
            raise TypeError("selected block record IDs must be a tuple")
        if len(self.selected_block_record_ids) > self.MAX_SELECTED_BLOCKS:
            raise TranscriptEvidenceSelectionLimitError(
                "selected block record ID count exceeds 256"
            )
        for record_id in self.selected_block_record_ids:
            if (
                type(record_id) is not str
                or not record_id
                or record_id != record_id.strip()
                or len(record_id) > self.MAX_ID_CHARACTERS
            ):
                raise ValueError(
                    "selected block record IDs must contain 1 to 512 "
                    "trimmed characters"
                )
        canonical_ids = tuple(sorted(self.selected_block_record_ids))
        object.__setattr__(self, "selected_block_record_ids", canonical_ids)
        object.__setattr__(
            self,
            "request_id",
            stable_id(
                "transcript-evidence-selection-request",
                self.transcript.result_id,
                canonical_ids,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriptEvidenceSelectionResult(DataObjectActionResult):
    """Bind selection intent to either exact evidence or a closed failure."""

    request: TranscriptEvidenceSelectionRequest
    transcript_result_id: str
    selector_implementation_identity: str
    outcome: TranscriptEvidenceSelectionOutcome
    pages: tuple[SelectedTranscriptPageEvidence, ...]
    blocks: tuple[SelectedTranscriptBlockEvidence, ...]
    selection_errors: tuple[str, ...]
    duplicate_block_record_ids: tuple[str, ...]
    missing_block_record_ids: tuple[str, ...]
    transcript_warnings: tuple[str, ...]
    warnings_requiring_inspection: tuple[str, ...]
    block_resolved_warning_inspection_possible: bool
    result_id: str = field(init=False)

    @property
    def request_id(self) -> str:
        """Return the identity of the exact bound selection request."""

        return self.request.request_id

    def __post_init__(self) -> None:
        if type(self.request) is not TranscriptEvidenceSelectionRequest:
            raise TypeError(
                "request must be a TranscriptEvidenceSelectionRequest"
            )
        if self.transcript_result_id != self.request.transcript.result_id:
            raise ValueError("result transcript does not match its request")
        if (
            type(self.selector_implementation_identity) is not str
            or not self.selector_implementation_identity
            or self.selector_implementation_identity
            != self.selector_implementation_identity.strip()
        ):
            raise ValueError("selector implementation identity is required")
        if type(self.outcome) is not TranscriptEvidenceSelectionOutcome:
            raise TypeError("selection outcome must be explicit")
        if self.transcript_warnings != self.request.transcript.warnings:
            raise ValueError("result must retain exact transcript warnings")
        if type(self.block_resolved_warning_inspection_possible) is not bool:
            raise TypeError("warning inspection capability must be boolean")
        if type(self.pages) is not tuple or any(
            type(page) is not SelectedTranscriptPageEvidence
            for page in self.pages
        ):
            raise TypeError("pages must contain selected page evidence")
        if type(self.blocks) is not tuple or any(
            type(block) is not SelectedTranscriptBlockEvidence
            for block in self.blocks
        ):
            raise TypeError("blocks must contain selected block evidence")
        for label, values in (
            ("selection errors", self.selection_errors),
            ("duplicate block record IDs", self.duplicate_block_record_ids),
            ("missing block record IDs", self.missing_block_record_ids),
            (
                "warnings requiring inspection",
                self.warnings_requiring_inspection,
            ),
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{label} must be sorted and unique")
        self._validate_outcome()
        self._validate_evidence()
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "transcript-evidence-selection-result",
                self.request.request_id,
                self.transcript_result_id,
                self.selector_implementation_identity,
                self.outcome,
                tuple(page.selected_page_evidence_id for page in self.pages),
                tuple(
                    block.selected_block_evidence_id for block in self.blocks
                ),
                self.selection_errors,
                self.duplicate_block_record_ids,
                self.missing_block_record_ids,
                self.transcript_warnings,
                self.warnings_requiring_inspection,
                self.block_resolved_warning_inspection_possible,
            ),
        )

    def _validate_outcome(self) -> None:
        failure_values = (
            self.selection_errors,
            self.duplicate_block_record_ids,
            self.missing_block_record_ids,
            self.warnings_requiring_inspection,
        )
        if self.outcome is TranscriptEvidenceSelectionOutcome.INVALID_SELECTION:
            if not self.selection_errors:
                raise ValueError("invalid selection requires selection errors")
        elif self.outcome is TranscriptEvidenceSelectionOutcome.MISSING_BLOCK:
            if not self.missing_block_record_ids:
                raise ValueError("missing-block outcome requires missing IDs")
        elif self.outcome is (
            TranscriptEvidenceSelectionOutcome.WARNING_INSPECTION_REQUIRED
        ):
            if not self.warnings_requiring_inspection:
                raise ValueError("inspection outcome requires warning codes")
        elif (
            self.outcome
            is TranscriptEvidenceSelectionOutcome.EVIDENCE_AVAILABLE
        ):
            if any(failure_values):
                raise ValueError("available evidence cannot retain failures")
            if not self.blocks or not self.pages:
                raise ValueError("available outcome requires selected evidence")
        elif self.outcome is not (
            TranscriptEvidenceSelectionOutcome.TRANSCRIPT_NOT_COMPLETE
        ):
            raise ValueError("unsupported selection outcome")

        if (
            self.outcome
            is not TranscriptEvidenceSelectionOutcome.EVIDENCE_AVAILABLE
            and (self.pages or self.blocks)
        ):
            raise ValueError("failed selection must expose no evidence")

    def _validate_evidence(self) -> None:
        if (
            self.outcome
            is not TranscriptEvidenceSelectionOutcome.EVIDENCE_AVAILABLE
        ):
            return
        if tuple(block.order_index for block in self.blocks) != tuple(
            sorted(block.order_index for block in self.blocks)
        ):
            raise ValueError(
                "selected blocks must use canonical transcript order"
            )
        if tuple(page.page_index for page in self.pages) != tuple(
            sorted(page.page_index for page in self.pages)
        ):
            raise ValueError("selected pages must use canonical page order")
        if {block.block_record_id for block in self.blocks} != set(
            self.request.selected_block_record_ids
        ):
            raise ValueError("selected evidence does not fulfill the request")
        expected_page_ids: list[str] = []
        for page in self.pages:
            page_blocks = tuple(
                block for block in self.blocks if block.page_id == page.page_id
            )
            if not page_blocks:
                raise ValueError("selected page must contain selected blocks")
            if page.transcript_result_id != self.transcript_result_id:
                raise ValueError("selected page has a different transcript")
            if any(
                block.page_index != page.page_index
                or block.printed_page_label != page.printed_page_label
                or block.transcript_result_id != self.transcript_result_id
                for block in page_blocks
            ):
                raise ValueError("selected block page evidence is inconsistent")
            if (
                page.selected_block_evidence_ids
                != tuple(
                    block.selected_block_evidence_id for block in page_blocks
                )
                or page.block_ids
                != tuple(block.block_id for block in page_blocks)
                or page.block_record_ids
                != tuple(block.block_record_id for block in page_blocks)
            ):
                raise ValueError(
                    "selected page block inventory is inconsistent"
                )
            expected_page_ids.append(page.page_id)
        if set(expected_page_ids) != {block.page_id for block in self.blocks}:
            raise ValueError("selected page inventory is incomplete")


__all__ = [
    "TranscriptEvidenceSelectionLimitError",
    "TranscriptEvidenceSelectionOutcome",
    "TranscriptEvidenceSelectionRequest",
    "TranscriptEvidenceSelectionResult",
]
