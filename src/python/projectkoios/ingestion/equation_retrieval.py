from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.equations import (
    EquationCandidate,
    EquationCandidateKind,
    EquationDetectionResult,
    EquationEvidenceStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import BoundingBox, SourceSpan

EQUATION_RETRIEVAL_CONTRACT_VERSION = "1.0"
_MAX_RECORDS = 256
_MAX_RETRIEVAL_TEXT_CHARACTERS = 32_768


class EquationRetrievalTranscriptionStatus(StrEnum):
    """Explicitly distinguishes native PDF text from math transcription."""

    NATIVE_TEXT_ONLY = "native_text_only"


@dataclass(frozen=True)
class EquationRetrievalRecord:
    """A compact, evidence-linked equation candidate for retrieval indexes."""

    record_id: str
    candidate_id: str
    kind: EquationCandidateKind
    evidence_status: EquationEvidenceStatus
    confidence: float
    page_index: int
    printed_page_label: str | None
    source_block_id: str
    source_spans: tuple[SourceSpan, ...]
    raw_text: str
    source_label: str | None
    preceding_context_block_id: str | None
    preceding_context_text: str | None
    following_context_block_id: str | None
    following_context_text: str | None
    retrieval_text: str
    rendered_region_id: str
    rendered_region_sha256: str
    source_bounding_box: BoundingBox
    warning_ids: tuple[str, ...]
    transcription_status: EquationRetrievalTranscriptionStatus = (
        EquationRetrievalTranscriptionStatus.NATIVE_TEXT_ONLY
    )
    contract_version: str = EQUATION_RETRIEVAL_CONTRACT_VERSION

    @classmethod
    def from_candidate(
        cls,
        candidate: EquationCandidate,
        *,
        block_text: dict[str, str],
    ) -> EquationRetrievalRecord:
        preceding_id = (
            candidate.preceding_context.block_id
            if candidate.preceding_context is not None
            else None
        )
        following_id = (
            candidate.following_context.block_id
            if candidate.following_context is not None
            else None
        )
        preceding = block_text.get(preceding_id) if preceding_id else None
        following = block_text.get(following_id) if following_id else None
        retrieval_text = _retrieval_text(
            candidate.raw_text,
            preceding=preceding,
            following=following,
        )
        record_id = stable_id(
            "equation-retrieval-record",
            EQUATION_RETRIEVAL_CONTRACT_VERSION,
            candidate.candidate_id,
            retrieval_text,
        )
        return cls(
            record_id=record_id,
            candidate_id=candidate.candidate_id,
            kind=candidate.kind,
            evidence_status=candidate.evidence_status,
            confidence=candidate.confidence,
            page_index=candidate.rendered_region.page_index,
            printed_page_label=candidate.rendered_region.printed_page_label,
            source_block_id=candidate.source_block_id,
            source_spans=candidate.source_spans,
            raw_text=candidate.raw_text,
            source_label=candidate.source_label,
            preceding_context_block_id=preceding_id,
            preceding_context_text=preceding,
            following_context_block_id=following_id,
            following_context_text=following,
            retrieval_text=retrieval_text,
            rendered_region_id=candidate.rendered_region.region_id,
            rendered_region_sha256=candidate.rendered_region.content_sha256,
            source_bounding_box=(candidate.rendered_region.source_bounding_box),
            warning_ids=candidate.warning_ids,
        )

    def __post_init__(self) -> None:
        for name, value in (
            ("record_id", self.record_id),
            ("candidate_id", self.candidate_id),
            ("source_block_id", self.source_block_id),
            ("raw_text", self.raw_text),
            ("retrieval_text", self.retrieval_text),
            ("rendered_region_id", self.rendered_region_id),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.kind, EquationCandidateKind):
            raise TypeError("kind must be EquationCandidateKind")
        if not isinstance(self.evidence_status, EquationEvidenceStatus):
            raise TypeError("evidence_status must be EquationEvidenceStatus")
        if not isinstance(
            self.transcription_status, EquationRetrievalTranscriptionStatus
        ):
            raise TypeError("unsupported equation transcription status")
        if self.contract_version != EQUATION_RETRIEVAL_CONTRACT_VERSION:
            raise ValueError("unsupported equation retrieval record version")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if self.page_index < 0:
            raise ValueError("page_index must be non-negative")
        if len(self.retrieval_text) > _MAX_RETRIEVAL_TEXT_CHARACTERS:
            raise ValueError("equation retrieval text exceeds the limit")
        if len(self.rendered_region_sha256) != 64:
            raise ValueError("rendered_region_sha256 must be a SHA-256 digest")
        try:
            int(self.rendered_region_sha256, 16)
        except ValueError as error:
            raise ValueError(
                "rendered_region_sha256 must be a SHA-256 digest"
            ) from error
        expected = stable_id(
            "equation-retrieval-record",
            EQUATION_RETRIEVAL_CONTRACT_VERSION,
            self.candidate_id,
            self.retrieval_text,
        )
        if self.record_id != expected:
            raise ValueError("equation retrieval record ID is inconsistent")


@dataclass(frozen=True)
class EquationRetrievalArtifact:
    """Retrieval records derived from exact equation detection evidence."""

    artifact_id: str
    source_id: str
    source_content_hash: str
    document_id: str
    detection_result_id: str
    detection_processor_name: str
    detection_processor_version: str
    detection_configuration_digest: str
    records: tuple[EquationRetrievalRecord, ...]
    contract_version: str = EQUATION_RETRIEVAL_CONTRACT_VERSION

    @classmethod
    def from_detection(
        cls,
        result: EquationDetectionResult,
    ) -> EquationRetrievalArtifact:
        if not isinstance(result, EquationDetectionResult):
            raise TypeError("result must be EquationDetectionResult")
        document = result.detection_input.document
        block_text = {
            block.block_id: block.text
            for page in document.pages
            for block in page.blocks
            if block.text is not None
        }
        records = tuple(
            EquationRetrievalRecord.from_candidate(
                candidate,
                block_text=block_text,
            )
            for candidate in result.candidates
        )
        artifact_id = stable_id(
            "equation-retrieval-artifact",
            EQUATION_RETRIEVAL_CONTRACT_VERSION,
            document.source.source_id,
            document.source.content_hash,
            document.document_id,
            result.result_id,
            tuple(record.record_id for record in records),
        )
        return cls(
            artifact_id=artifact_id,
            source_id=document.source.source_id,
            source_content_hash=document.source.content_hash,
            document_id=document.document_id,
            detection_result_id=result.result_id,
            detection_processor_name=result.processor_name,
            detection_processor_version=result.processor_version,
            detection_configuration_digest=result.configuration_digest,
            records=records,
        )

    def __post_init__(self) -> None:
        if self.contract_version != EQUATION_RETRIEVAL_CONTRACT_VERSION:
            raise ValueError("unsupported equation retrieval artifact version")
        for name, value in (
            ("artifact_id", self.artifact_id),
            ("source_id", self.source_id),
            ("source_content_hash", self.source_content_hash),
            ("document_id", self.document_id),
            ("detection_result_id", self.detection_result_id),
            ("detection_processor_name", self.detection_processor_name),
            ("detection_processor_version", self.detection_processor_version),
            (
                "detection_configuration_digest",
                self.detection_configuration_digest,
            ),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.records, tuple):
            raise TypeError("records must be an immutable tuple")
        if len(self.records) > _MAX_RECORDS:
            raise ValueError(
                "equation retrieval record count exceeds the limit"
            )
        if any(
            not isinstance(record, EquationRetrievalRecord)
            for record in self.records
        ):
            raise TypeError(
                "records must contain EquationRetrievalRecord values"
            )
        record_ids = tuple(record.record_id for record in self.records)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("equation retrieval record IDs must be unique")
        expected = stable_id(
            "equation-retrieval-artifact",
            EQUATION_RETRIEVAL_CONTRACT_VERSION,
            self.source_id,
            self.source_content_hash,
            self.document_id,
            self.detection_result_id,
            record_ids,
        )
        if self.artifact_id != expected:
            raise ValueError("equation retrieval artifact ID is inconsistent")


def _retrieval_text(
    raw_text: str,
    *,
    preceding: str | None,
    following: str | None,
) -> str:
    parts: list[str] = []
    if preceding:
        parts.append(f"Preceding context:\n{preceding.strip()}")
    parts.append(f"Equation candidate (native PDF text):\n{raw_text.strip()}")
    if following:
        parts.append(f"Following context:\n{following.strip()}")
    return "\n\n".join(parts)
