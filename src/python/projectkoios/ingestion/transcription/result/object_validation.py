from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.models import IngestionWarning
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.omission.omission import (
    TranscriptionOmission,
)
from projectkoios.ingestion.transcription.omission.validation.coverage import (
    TranscriptionOmissionCoverageValidation,
)
from projectkoios.ingestion.transcription.request.request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.source.validation.coverage import (
    TranscriptionSourceCoverageValidation,
)
from projectkoios.ingestion.transcription.source.validation.item import (
    TranscriptionItemSourceValidation,
)


@dataclass(frozen=True)
class TranscriptionResultObjectValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    result_id: str
    transcription_input: StructuredTranscriptionRequest
    items: tuple[TranscriptionItem, ...]
    omissions: tuple[TranscriptionOmission, ...]
    warnings: tuple[IngestionWarning, ...]
    item_validations: tuple[TranscriptionItemSourceValidation, ...]
    omission_validation: TranscriptionOmissionCoverageValidation
    source_coverage_validation: TranscriptionSourceCoverageValidation
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def validate(
        cls,
        result_id: str,
        transcription_input: StructuredTranscriptionRequest,
        items: tuple[TranscriptionItem, ...],
        omissions: tuple[TranscriptionOmission, ...],
        warnings: tuple[IngestionWarning, ...],
    ) -> TranscriptionResultObjectValidation:
        warning_by_id = {warning.warning_id: warning for warning in warnings}
        item_validations = tuple(
            TranscriptionItemSourceValidation(
                transcription_input,
                item,
                tuple(warning_by_id[value] for value in item.warning_ids),
            )
            for item in items
        )
        omission_validation = TranscriptionOmissionCoverageValidation(
            transcription_input, items, omissions
        )
        source_coverage_validation = TranscriptionSourceCoverageValidation(
            transcription_input, items
        )
        return cls(
            result_id,
            transcription_input,
            items,
            omissions,
            warnings,
            item_validations,
            omission_validation,
            source_coverage_validation,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported result-object validation version")
        self.validate_identity_fields(self.result_id)
        if tuple(value.item for value in self.item_validations) != self.items:
            raise ValueError("item-source validations are incomplete")
        if any(
            value.transcription_input != self.transcription_input
            for value in self.item_validations
        ):
            raise ValueError("item-source validation input is inconsistent")
        warning_by_id = {
            warning.warning_id: warning for warning in self.warnings
        }
        if any(
            value.warnings
            != tuple(
                warning_by_id[warning_id]
                for warning_id in value.item.warning_ids
            )
            for value in self.item_validations
        ):
            raise ValueError("item-source validation warnings are inconsistent")
        if (
            self.omission_validation.transcription_input
            != self.transcription_input
        ):
            raise ValueError("omission validation input is inconsistent")
        if self.omission_validation.items != self.items:
            raise ValueError("omission validation items are inconsistent")
        if self.omission_validation.omissions != self.omissions:
            raise ValueError("omission validation is inconsistent")
        if (
            self.source_coverage_validation.transcription_input
            != self.transcription_input
            or self.source_coverage_validation.items != self.items
        ):
            raise ValueError("source coverage validation is inconsistent")

    @property
    def validated_item_count(self) -> int:
        return len(self.item_validations)

    @property
    def validated_omission_count(self) -> int:
        return len(self.omissions)
