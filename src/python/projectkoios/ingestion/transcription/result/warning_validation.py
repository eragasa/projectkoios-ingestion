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
from projectkoios.ingestion.transcription.result.result import (
    StructuredTranscriptionResult,
)


@dataclass(frozen=True)
class TranscriptionWarningValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    result_id: str
    validated_warning_count: int
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls, result: StructuredTranscriptionResult, valid_object_ids: set[str]
    ) -> TranscriptionWarningValidation:
        for warning in result.warnings:
            cls._validate_composition_warning(
                warning, result.transcription_input.document, valid_object_ids
            )
        return cls(result.result_id, len(result.warnings))

    @staticmethod
    def _validate_composition_warning(
        warning: IngestionWarning,
        document: ExtractedDocument,
        valid_object_ids: set[str],
    ) -> None:
        AbstractTranscriptionDataObject._bounded_string(
            "warning code", warning.code, nonempty=True
        )
        AbstractTranscriptionDataObject._bounded_string(
            "warning message",
            warning.message,
            nonempty=True,
            limit=AbstractTranscriptionDataObject.MAX_TEXT_CHARACTERS_PER_ITEM,
        )
        if not isinstance(warning.severity, WarningSeverity):
            raise TypeError("transcription warning severity is unsupported")
        AbstractTranscriptionDataObject._unique_strings(
            "warning object IDs", warning.object_ids
        )
        if not set(warning.object_ids).issubset(valid_object_ids):
            raise ValueError("transcription warning object link is unresolved")
        AbstractTranscriptionDataObject._validate_exact_source_spans(
            warning.source_spans, document
        )
        AbstractTranscriptionDataObject._validate_metadata(warning.evidence)
        if warning.suggested_recovery is not None:
            AbstractTranscriptionDataObject._bounded_string(
                "warning suggested recovery",
                warning.suggested_recovery,
                nonempty=True,
                limit=AbstractTranscriptionDataObject.MAX_TEXT_CHARACTERS_PER_ITEM,
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
