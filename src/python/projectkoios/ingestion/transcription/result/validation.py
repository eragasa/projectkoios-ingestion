from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
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
from projectkoios.ingestion.transcription.result.limit_validation import (
    TranscriptionResultLimitValidation,
)
from projectkoios.ingestion.transcription.result.object_validation import (
    TranscriptionResultObjectValidation,
)
from projectkoios.ingestion.transcription.result.result import (
    StructuredTranscriptionResult,
)
from projectkoios.ingestion.transcription.result.warning_validation import (
    TranscriptionWarningValidation,
)


@dataclass(frozen=True)
class TranscriptionResultValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    result_id: str
    validated_item_count: int
    validated_omission_count: int
    validated_warning_count: int
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def create(
        cls, result: StructuredTranscriptionResult
    ) -> TranscriptionResultValidation:
        cls._validate_result(result)
        return cls(
            result_id=result.result_id,
            validated_item_count=len(result.items),
            validated_omission_count=len(result.omissions),
            validated_warning_count=len(result.warnings),
        )

    @staticmethod
    def _validate_result(result: StructuredTranscriptionResult) -> None:
        if not isinstance(
            result.transcription_input, StructuredTranscriptionRequest
        ):
            raise TypeError("transcription result input is unsupported")
        AbstractTranscriptionDataObject._require_tuple(
            "transcription items", result.items
        )
        AbstractTranscriptionDataObject._require_tuple(
            "transcription omissions", result.omissions
        )
        AbstractTranscriptionDataObject._require_tuple(
            "transcription warnings", result.warnings
        )
        if any(
            not isinstance(item, TranscriptionItem) for item in result.items
        ):
            raise TypeError("transcription items contain an unsupported value")
        if any(
            not isinstance(item, TranscriptionOmission)
            for item in result.omissions
        ):
            raise TypeError(
                "transcription omissions contain an unsupported value"
            )
        if any(
            not isinstance(item, IngestionWarning) for item in result.warnings
        ):
            raise TypeError(
                "transcription warnings contain an unsupported value"
            )
        AbstractTranscriptionDataObject._identity_fields(
            result.processor_name, result.processor_version
        )
        configuration = result.transcription_input.configuration
        if result.configuration_digest != configuration.configuration_digest:
            raise ValueError(
                "transcription configuration digest is inconsistent"
            )
        expected_cache = TranscriptionCacheIdentity.create(
            result.transcription_input,
            processor_name=result.processor_name,
            processor_version=result.processor_version,
        ).cache_key
        if result.cache_key != expected_cache:
            raise ValueError("transcription cache key is inconsistent")
        if tuple(item.order_index for item in result.items) != tuple(
            range(len(result.items))
        ):
            raise ValueError(
                "transcription item order indices are inconsistent"
            )
        item_ids = tuple(item.item_id for item in result.items)
        omission_ids = tuple(item.omission_id for item in result.omissions)
        warning_ids = tuple(item.warning_id for item in result.warnings)
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("transcription item IDs must be unique")
        source_object_keys = tuple(
            (item.source_object_kind, item.source_object_id)
            for item in result.items
        )
        if len(set(source_object_keys)) != len(source_object_keys):
            raise ValueError("transcription source objects must be unique")
        if len(set(omission_ids)) != len(omission_ids):
            raise ValueError("transcription omission IDs must be unique")
        omission_source_keys = tuple(
            (item.omitted_object_id, item.source_block_id)
            for item in result.omissions
        )
        if len(set(omission_source_keys)) != len(omission_source_keys):
            raise ValueError("transcription omission sources must be unique")
        if len(set(warning_ids)) != len(warning_ids):
            raise ValueError("transcription warning IDs must be unique")
        if any(
            not set(item.warning_ids).issubset(warning_ids)
            for item in result.items
        ):
            raise ValueError("transcription item warning link is unresolved")
        if any(
            not set(item.warning_ids).issubset(warning_ids)
            for item in result.omissions
        ):
            raise ValueError(
                "transcription omission warning link is unresolved"
            )
        if any(
            not set(item.represented_by_item_ids).issubset(item_ids)
            for item in result.omissions
        ):
            raise ValueError("transcription omission item link is unresolved")
        valid_warning_object_ids = (
            set(item_ids)
            | {item.source_object_id for item in result.items}
            | set(omission_ids)
            | {item.source_block_id for item in result.omissions}
        )
        TranscriptionWarningValidation.create(result, valid_warning_object_ids)
        TranscriptionResultObjectValidation.create(result)
        if result.status is not type(result)._result_status(
            result.items, result.omissions, result.warnings
        ):
            raise ValueError("transcription status is inconsistent")
        TranscriptionResultLimitValidation.create(result, configuration)
