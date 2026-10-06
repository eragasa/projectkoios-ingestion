"""Selected page and block evidence records."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.base import DataObjectModel
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import Metadata
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


class TranscriptEvidenceMappingBasis(StrEnum):
    """Identify how clean indexed text maps to retained raw text."""

    CLEAN_TRANSCRIPT_BLOCK_EXACT_PAIR = "CLEAN_TRANSCRIPT_BLOCK_EXACT_PAIR"


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
        return SHA256Fingerprinter.fingerprint(content=text.encode("utf-8"))


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


__all__ = [
    "SelectedTranscriptBlockEvidence",
    "SelectedTranscriptPageEvidence",
    "TranscriptEvidenceMappingBasis",
]
