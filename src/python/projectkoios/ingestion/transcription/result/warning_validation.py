from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedDocument,
    IngestionWarning,
    WarningSeverity,
)
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)


@dataclass(frozen=True)
class TranscriptionWarningValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    result_id: str
    document: ExtractedDocument
    warnings: tuple[IngestionWarning, ...]
    valid_object_ids: tuple[str, ...]
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription warning validation version"
            )
        self.validate_identity_fields(self.result_id)
        self.validate_tuple("transcription warnings", self.warnings)
        self.validate_unique_strings(
            "valid warning object IDs", self.valid_object_ids
        )
        valid_object_ids = set(self.valid_object_ids)
        for warning in self.warnings:
            self.validate_bounded_string(
                "warning code", warning.code, nonempty=True
            )
            self.validate_bounded_string(
                "warning message",
                warning.message,
                nonempty=True,
                limit=self.MAX_TEXT_CHARACTERS_PER_ITEM,
            )
            if not isinstance(warning.severity, WarningSeverity):
                raise TypeError("transcription warning severity is unsupported")
            self.validate_unique_strings(
                "warning object IDs", warning.object_ids
            )
            if not set(warning.object_ids).issubset(valid_object_ids):
                raise ValueError(
                    "transcription warning object link is unresolved"
                )
            self.validate_exact_source_spans(
                warning.source_spans, self.document
            )
            self.validate_metadata(warning.evidence)
            if warning.suggested_recovery is not None:
                self.validate_bounded_string(
                    "warning suggested recovery",
                    warning.suggested_recovery,
                    nonempty=True,
                    limit=self.MAX_TEXT_CHARACTERS_PER_ITEM,
                )
            expected = stable_id(
                "warning",
                warning.code,
                warning.object_ids,
                tuple(span.identity_parts() for span in warning.source_spans),
                warning.evidence,
            )
            if warning.warning_id != expected:
                raise ValueError("transcription warning ID is inconsistent")

    @property
    def validated_warning_count(self) -> int:
        return len(self.warnings)
