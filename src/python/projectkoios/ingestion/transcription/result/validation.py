from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.models import IngestionWarning
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
from projectkoios.ingestion.transcription.result.limit_validation import (
    TranscriptionResultLimitValidation,
)
from projectkoios.ingestion.transcription.result.object_validation import (
    TranscriptionResultObjectValidation,
)
from projectkoios.ingestion.transcription.result.status import (
    TranscriptionStatus,
)
from projectkoios.ingestion.transcription.result.warning_validation import (
    TranscriptionWarningValidation,
)


@dataclass(frozen=True)
class TranscriptionResultValidation(
    AbstractValidation, AbstractTranscriptionDataObject
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
    warning_validation: TranscriptionWarningValidation
    object_validation: TranscriptionResultObjectValidation
    limit_validation: TranscriptionResultLimitValidation
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def validate(
        cls,
        *,
        result_id: str,
        transcription_input: StructuredTranscriptionRequest,
        items: tuple[TranscriptionItem, ...],
        omissions: tuple[TranscriptionOmission, ...],
        warnings: tuple[IngestionWarning, ...],
        status: TranscriptionStatus,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
        cache_key: str,
    ) -> TranscriptionResultValidation:
        item_ids = tuple(item.item_id for item in items)
        omission_ids = tuple(item.omission_id for item in omissions)
        valid_warning_object_ids = tuple(
            dict.fromkeys(
                item_ids
                + tuple(item.source_object_id for item in items)
                + omission_ids
                + tuple(item.source_block_id for item in omissions)
            )
        )
        warning_validation = TranscriptionWarningValidation(
            result_id,
            transcription_input.document,
            warnings,
            valid_warning_object_ids,
        )
        object_validation = TranscriptionResultObjectValidation.validate(
            result_id,
            transcription_input,
            items,
            omissions,
            warnings,
        )
        limit_validation = TranscriptionResultLimitValidation(
            result_id,
            items,
            omissions,
            warnings,
            transcription_input.configuration,
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
            configuration_digest=configuration_digest,
            cache_key=cache_key,
            warning_validation=warning_validation,
            object_validation=object_validation,
            limit_validation=limit_validation,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription result validation version"
            )
        if not isinstance(
            self.transcription_input, StructuredTranscriptionRequest
        ):
            raise TypeError("transcription result input is unsupported")
        self.validate_tuple("transcription items", self.items)
        self.validate_tuple("transcription omissions", self.omissions)
        self.validate_tuple("transcription warnings", self.warnings)
        if any(not isinstance(item, TranscriptionItem) for item in self.items):
            raise TypeError("transcription items contain an unsupported value")
        if any(
            not isinstance(item, TranscriptionOmission)
            for item in self.omissions
        ):
            raise TypeError(
                "transcription omissions contain an unsupported value"
            )
        if any(
            not isinstance(item, IngestionWarning) for item in self.warnings
        ):
            raise TypeError(
                "transcription warnings contain an unsupported value"
            )
        self.validate_identity_fields(
            self.result_id, self.processor_name, self.processor_version
        )
        configuration = self.transcription_input.configuration
        if self.configuration_digest != configuration.configuration_digest:
            raise ValueError(
                "transcription configuration digest is inconsistent"
            )
        expected_cache = TranscriptionCacheIdentity.create(
            self.transcription_input,
            processor_name=self.processor_name,
            processor_version=self.processor_version,
        ).cache_key
        if self.cache_key != expected_cache:
            raise ValueError("transcription cache key is inconsistent")
        if tuple(item.order_index for item in self.items) != tuple(
            range(len(self.items))
        ):
            raise ValueError(
                "transcription item order indices are inconsistent"
            )
        item_ids = tuple(item.item_id for item in self.items)
        omission_ids = tuple(item.omission_id for item in self.omissions)
        warning_ids = tuple(item.warning_id for item in self.warnings)
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("transcription item IDs must be unique")
        source_object_keys = tuple(
            (item.source_object_kind, item.source_object_id)
            for item in self.items
        )
        if len(set(source_object_keys)) != len(source_object_keys):
            raise ValueError("transcription source objects must be unique")
        if len(set(omission_ids)) != len(omission_ids):
            raise ValueError("transcription omission IDs must be unique")
        omission_source_keys = tuple(
            (item.omitted_object_id, item.source_block_id)
            for item in self.omissions
        )
        if len(set(omission_source_keys)) != len(omission_source_keys):
            raise ValueError("transcription omission sources must be unique")
        if len(set(warning_ids)) != len(warning_ids):
            raise ValueError("transcription warning IDs must be unique")
        if any(
            not set(item.warning_ids).issubset(warning_ids)
            for item in self.items
        ):
            raise ValueError("transcription item warning link is unresolved")
        if any(
            not set(item.warning_ids).issubset(warning_ids)
            for item in self.omissions
        ):
            raise ValueError(
                "transcription omission warning link is unresolved"
            )
        if any(
            not set(item.represented_by_item_ids).issubset(item_ids)
            for item in self.omissions
        ):
            raise ValueError("transcription omission item link is unresolved")
        if self.status is not TranscriptionStatus.determine(
            self.items, self.omissions, self.warnings
        ):
            raise ValueError("transcription status is inconsistent")
        expected_warning_object_ids = tuple(
            dict.fromkeys(
                item_ids
                + tuple(item.source_object_id for item in self.items)
                + omission_ids
                + tuple(item.source_block_id for item in self.omissions)
            )
        )
        if (
            self.warning_validation.result_id != self.result_id
            or self.warning_validation.document
            != self.transcription_input.document
            or self.warning_validation.warnings != self.warnings
            or self.warning_validation.valid_object_ids
            != expected_warning_object_ids
        ):
            raise ValueError("warning validation result is inconsistent")
        if (
            self.object_validation.result_id != self.result_id
            or self.object_validation.transcription_input
            != self.transcription_input
            or self.object_validation.items != self.items
            or self.object_validation.omissions != self.omissions
            or self.object_validation.warnings != self.warnings
        ):
            raise ValueError("object validation result is inconsistent")
        if (
            self.limit_validation.result_id != self.result_id
            or self.limit_validation.items != self.items
            or self.limit_validation.omissions != self.omissions
            or self.limit_validation.warnings != self.warnings
            or self.limit_validation.configuration != configuration
        ):
            raise ValueError("limit validation result is inconsistent")
        self.validate_retained_size(
            (
                self.result_id,
                self.transcription_input,
                self.items,
                self.omissions,
                self.warnings,
                self.status,
                self.processor_name,
                self.processor_version,
                self.configuration_digest,
                self.cache_key,
            ),
            configuration.max_result_bytes,
        )

    @property
    def validated_item_count(self) -> int:
        return len(self.items)

    @property
    def validated_omission_count(self) -> int:
        return len(self.omissions)

    @property
    def validated_warning_count(self) -> int:
        return len(self.warnings)
