from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.structured_request import (
    StructuredTranscriptionRequest,
)


@dataclass(frozen=True)
class TranscriptionCacheIdentity(
    AbstractIdentity,
    AbstractTranscriptionDataObject,
):
    cache_key: str
    input_id: str
    processor_name: str
    processor_version: str
    configuration_identity: tuple[object, ...]
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        transcription_input: StructuredTranscriptionRequest,
        *,
        processor_name: str = "deterministic-structured-transcription-composer",
        processor_version: str | None = None,
    ) -> TranscriptionCacheIdentity:
        if processor_version is None:
            processor_version = cls.COMPOSER_VERSION
        if not isinstance(transcription_input, StructuredTranscriptionRequest):
            raise TypeError(
                "transcription_input must be StructuredTranscriptionRequest"
            )
        cls.validate_identity_fields(processor_name, processor_version)
        return cls(
            cache_key=stable_id(
                "structured-transcription-cache",
                cls.CONTRACT_VERSION,
                cls.CONFIGURATION_VERSION,
                transcription_input.input_id,
                processor_name,
                processor_version,
                transcription_input.configuration.identity_parts(),
            ),
            input_id=transcription_input.input_id,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_identity=transcription_input.configuration.identity_parts(),
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported transcription cache identity version")
        self.validate_identity_fields(
            self.cache_key,
            self.input_id,
            self.processor_name,
            self.processor_version,
        )
        self.validate_tuple(
            "transcription configuration identity", self.configuration_identity
        )
        expected = stable_id(
            "structured-transcription-cache",
            self.CONTRACT_VERSION,
            self.CONFIGURATION_VERSION,
            self.input_id,
            self.processor_name,
            self.processor_version,
            self.configuration_identity,
        )
        if self.cache_key != expected:
            raise ValueError("transcription cache identity is inconsistent")
