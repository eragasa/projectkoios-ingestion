from __future__ import annotations

from dataclasses import dataclass

from projectkoios.base import (
    DataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    IngestionWarning,
)
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.cache.identity import (
    TranscriptionCacheIdentity,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.omission.omission import (
    TranscriptionOmission,
)
from projectkoios.ingestion.transcription.request.request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.result.status import (
    TranscriptionStatus,
)
from projectkoios.ingestion.transcription.result.validation import (
    TranscriptionResultValidation,
)


@dataclass(frozen=True)
class StructuredTranscriptionResult(
    DataObjectActionResult, AbstractTranscriptionDataObject
):
    result_id: str
    transcription_input: StructuredTranscriptionRequest
    items: tuple[TranscriptionItem, ...]
    omissions: tuple[TranscriptionOmission, ...]
    warnings: tuple[IngestionWarning, ...]
    status: TranscriptionStatus
    processor_name: str
    processor_version: str
    configuration_digest: str
    cache_key: str
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        transcription_input: StructuredTranscriptionRequest,
        items: tuple[TranscriptionItem, ...],
        omissions: tuple[TranscriptionOmission, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> StructuredTranscriptionResult:
        digest = transcription_input.configuration.configuration_digest
        cache_key = TranscriptionCacheIdentity.create(
            transcription_input,
            processor_name=processor_name,
            processor_version=processor_version,
        ).cache_key
        status = TranscriptionStatus.determine(items, omissions, warnings)
        result_id = StructuredTranscriptionResult.identity_for(
            transcription_input.input_id,
            items,
            omissions,
            warnings,
            status,
            processor_name,
            processor_version,
            digest,
            cache_key,
        )
        return cls(
            result_id=result_id,
            transcription_input=transcription_input,
            items=items,
            omissions=omissions,
            warnings=warnings,
            status=status,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=digest,
            cache_key=cache_key,
        )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != AbstractTranscriptionDataObject.CONTRACT_VERSION
        ):
            raise ValueError("unsupported structured transcription version")
        validation = self.validation
        if validation.result_id != self.result_id:
            raise ValueError(
                "structured transcription validation is inconsistent"
            )
        expected = StructuredTranscriptionResult.identity_for(
            self.transcription_input.input_id,
            self.items,
            self.omissions,
            self.warnings,
            self.status,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
            self.cache_key,
        )
        if self.result_id != expected:
            raise ValueError(
                "structured transcription result ID is inconsistent"
            )

    @property
    def validation(self) -> TranscriptionResultValidation:
        return TranscriptionResultValidation.validate(
            result_id=self.result_id,
            transcription_input=self.transcription_input,
            items=self.items,
            omissions=self.omissions,
            warnings=self.warnings,
            status=self.status,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
            configuration_digest=self.configuration_digest,
            cache_key=self.cache_key,
        )

    @property
    def request(self) -> StructuredTranscriptionRequest:
        return self.transcription_input

    @property
    def request_id(self) -> str:
        return self.transcription_input.request_id

    @property
    def actionizer_name(self) -> str:
        return self.processor_name

    @property
    def actionizer_version(self) -> str:
        return self.processor_version

    @classmethod
    def identity_for(
        cls,
        input_id: str,
        items: tuple[TranscriptionItem, ...],
        omissions: tuple[TranscriptionOmission, ...],
        warnings: tuple[IngestionWarning, ...],
        status: TranscriptionStatus,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
        cache_key: str,
    ) -> str:
        return stable_id(
            "structured-transcription-result",
            input_id,
            tuple(
                (
                    item.item_id,
                    item.order_index,
                    item.order_status.value,
                    item.warning_ids,
                )
                for item in items
            ),
            tuple(item.omission_id for item in omissions),
            tuple(warning.warning_id for warning in warnings),
            status.value,
            processor_name,
            processor_version,
            configuration_digest,
            cache_key,
        )
