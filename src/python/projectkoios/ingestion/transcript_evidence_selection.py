"""Bounded clean-transcript evidence selection for downstream authoring."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
    DataObjectModel,
)
from projectkoios.ingestion.clean_transcript import (
    CleanTranscript,
    CleanTranscriptBlock,
    CleanTranscriptPage,
    CleanTranscriptStatus,
    DehyphenationOutcome,
    PageNumberOutcome,
    PublisherFrontMatterKind,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata

__all__ = [
    "SelectedTranscriptBlockEvidence",
    "SelectedTranscriptPageEvidence",
    "TranscriptEvidenceMappingBasis",
    "TranscriptEvidenceSelectionLimitError",
    "TranscriptEvidenceSelectionOutcome",
    "TranscriptEvidenceSelectionRequest",
    "TranscriptEvidenceSelectionResult",
    "TranscriptEvidenceSelector",
]


class TranscriptEvidenceSelectionLimitError(ValueError):
    """Raised before a transcript evidence selection exceeds a hard bound."""


class TranscriptEvidenceSelectionOutcome(StrEnum):
    """Closed outcomes for one clean-transcript evidence selection."""

    INVALID_SELECTION = "INVALID_SELECTION"
    MISSING_BLOCK = "MISSING_BLOCK"
    TRANSCRIPT_NOT_COMPLETE = "TRANSCRIPT_NOT_COMPLETE"
    WARNING_INSPECTION_REQUIRED = "WARNING_INSPECTION_REQUIRED"
    EVIDENCE_AVAILABLE = "EVIDENCE_AVAILABLE"


class TranscriptEvidenceMappingBasis(StrEnum):
    """Identify how clean indexed text maps to retained raw text."""

    CLEAN_TRANSCRIPT_BLOCK_EXACT_PAIR = "CLEAN_TRANSCRIPT_BLOCK_EXACT_PAIR"


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
class SelectedTranscriptBlockEvidence(DataObjectModel):
    """Retain exact paired clean and raw text for one selected block."""

    transcript_result_id: str
    page_id: str
    page_index: int
    printed_page_label: str | None
    block_id: str
    block_record_id: str
    order_index: int
    indexed_clean_text: str
    retained_raw_text: str
    mapping_basis: TranscriptEvidenceMappingBasis
    transformation_evidence: Metadata
    dehyphenation_decision_ids: tuple[str, ...]
    indexed_clean_text_sha256: str = field(init=False)
    retained_raw_text_sha256: str = field(init=False)
    selected_block_evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        for label, value in (
            ("transcript result ID", self.transcript_result_id),
            ("page ID", self.page_id),
            ("block ID", self.block_id),
            ("block record ID", self.block_record_id),
        ):
            if type(value) is not str or not value:
                raise ValueError(f"{label} must be nonempty")
        if (
            type(self.page_index) is not int
            or self.page_index < 0
            or type(self.order_index) is not int
            or self.order_index < 0
        ):
            raise ValueError("page and order indexes must be nonnegative ints")
        if (
            type(self.indexed_clean_text) is not str
            or not self.indexed_clean_text
            or type(self.retained_raw_text) is not str
            or not self.retained_raw_text
        ):
            raise ValueError("selected block text must be nonempty strings")
        expected_mapping_basis = (
            TranscriptEvidenceMappingBasis.CLEAN_TRANSCRIPT_BLOCK_EXACT_PAIR
        )
        if self.mapping_basis is not expected_mapping_basis:
            raise ValueError("unsupported clean-to-raw mapping basis")
        if type(
            self.transformation_evidence
        ) is not tuple or self.transformation_evidence != tuple(
            sorted(self.transformation_evidence)
        ):
            raise ValueError("transformation evidence must be a sorted tuple")
        if (
            type(self.dehyphenation_decision_ids) is not tuple
            or any(
                type(value) is not str or not value
                for value in self.dehyphenation_decision_ids
            )
            or len(self.dehyphenation_decision_ids)
            != len(set(self.dehyphenation_decision_ids))
        ):
            raise ValueError(
                "dehyphenation decision IDs must be unique strings"
            )
        clean_digest = self._digest(self.indexed_clean_text)
        raw_digest = self._digest(self.retained_raw_text)
        object.__setattr__(self, "indexed_clean_text_sha256", clean_digest)
        object.__setattr__(self, "retained_raw_text_sha256", raw_digest)
        object.__setattr__(
            self,
            "selected_block_evidence_id",
            stable_id(
                "selected-transcript-block-evidence",
                self.transcript_result_id,
                self.page_id,
                self.page_index,
                self.printed_page_label,
                self.block_id,
                self.block_record_id,
                self.order_index,
                clean_digest,
                raw_digest,
                self.mapping_basis,
                self.transformation_evidence,
                self.dehyphenation_decision_ids,
            ),
        )

    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectedTranscriptPageEvidence(DataObjectModel):
    """Group selected block evidence under one exact transcript page."""

    transcript_result_id: str
    page_id: str
    page_index: int
    printed_page_label: str | None
    selected_block_evidence_ids: tuple[str, ...]
    block_ids: tuple[str, ...]
    block_record_ids: tuple[str, ...]
    selected_page_evidence_id: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.transcript_result_id) is not str
            or not self.transcript_result_id
            or type(self.page_id) is not str
            or not self.page_id
        ):
            raise ValueError("transcript and page identities must be strings")
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("page index must be a nonnegative int")
        sizes = {
            len(self.selected_block_evidence_ids),
            len(self.block_ids),
            len(self.block_record_ids),
        }
        if sizes == {0} or len(sizes) != 1:
            raise ValueError("page evidence must contain aligned block IDs")
        for values in (
            self.selected_block_evidence_ids,
            self.block_ids,
            self.block_record_ids,
        ):
            if type(values) is not tuple or any(
                type(value) is not str or not value for value in values
            ):
                raise ValueError(
                    "page block identities must be nonempty tuples"
                )
            if len(values) != len(set(values)):
                raise ValueError("page block identities must be unique")
        object.__setattr__(
            self,
            "selected_page_evidence_id",
            stable_id(
                "selected-transcript-page-evidence",
                self.transcript_result_id,
                self.page_id,
                self.page_index,
                self.printed_page_label,
                self.selected_block_evidence_ids,
                self.block_ids,
                self.block_record_ids,
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
        ):
            if self.pages or self.blocks:
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
                dehyphenation_decision_ids=(block.dehyphenation_decision_ids),
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
