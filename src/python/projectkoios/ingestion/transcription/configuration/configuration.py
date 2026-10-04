from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.configuration.error import (
    TranscriptionLimitError,
)


@dataclass(frozen=True)
class TranscriptionConfiguration(AbstractTranscriptionDataObject):
    configuration_version: str = (
        AbstractTranscriptionDataObject.CONFIGURATION_VERSION
    )
    normalization_method: str = (
        AbstractTranscriptionDataObject.NORMALIZATION_METHOD
    )
    max_input_blocks: int = AbstractTranscriptionDataObject.MAX_INPUT_BLOCKS
    max_input_nodes: int = AbstractTranscriptionDataObject.MAX_INPUT_NODES
    max_typed_objects: int = AbstractTranscriptionDataObject.MAX_TYPED_OBJECTS
    max_items: int = AbstractTranscriptionDataObject.MAX_ITEMS
    max_omissions: int = AbstractTranscriptionDataObject.MAX_OMISSIONS
    max_warnings: int = AbstractTranscriptionDataObject.MAX_WARNINGS
    max_source_spans: int = AbstractTranscriptionDataObject.MAX_SOURCE_SPANS
    max_text_characters_per_item: int = (
        AbstractTranscriptionDataObject.MAX_TEXT_CHARACTERS_PER_ITEM
    )
    max_total_text_characters: int = (
        AbstractTranscriptionDataObject.MAX_TOTAL_TEXT_CHARACTERS
    )
    max_input_artifact_bytes: int = (
        AbstractTranscriptionDataObject.MAX_INPUT_ARTIFACT_BYTES
    )
    max_result_bytes: int = AbstractTranscriptionDataObject.MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        if (
            self.configuration_version
            != AbstractTranscriptionDataObject.CONFIGURATION_VERSION
        ):
            raise ValueError("unsupported transcription configuration version")
        if (
            self.normalization_method
            != AbstractTranscriptionDataObject.NORMALIZATION_METHOD
        ):
            raise ValueError("unsupported transcription normalization method")
        for name, hard_limit in (
            (
                "max_input_blocks",
                AbstractTranscriptionDataObject.MAX_INPUT_BLOCKS,
            ),
            (
                "max_input_nodes",
                AbstractTranscriptionDataObject.MAX_INPUT_NODES,
            ),
            (
                "max_typed_objects",
                AbstractTranscriptionDataObject.MAX_TYPED_OBJECTS,
            ),
            ("max_items", AbstractTranscriptionDataObject.MAX_ITEMS),
            ("max_omissions", AbstractTranscriptionDataObject.MAX_OMISSIONS),
            ("max_warnings", AbstractTranscriptionDataObject.MAX_WARNINGS),
            (
                "max_source_spans",
                AbstractTranscriptionDataObject.MAX_SOURCE_SPANS,
            ),
            (
                "max_text_characters_per_item",
                AbstractTranscriptionDataObject.MAX_TEXT_CHARACTERS_PER_ITEM,
            ),
            (
                "max_total_text_characters",
                AbstractTranscriptionDataObject.MAX_TOTAL_TEXT_CHARACTERS,
            ),
            (
                "max_input_artifact_bytes",
                AbstractTranscriptionDataObject.MAX_INPUT_ARTIFACT_BYTES,
            ),
            (
                "max_result_bytes",
                AbstractTranscriptionDataObject.MAX_RESULT_BYTES,
            ),
        ):
            value = getattr(self, name)
            AbstractTranscriptionDataObject.validate_positive_integer(
                name, value
            )
            if value > hard_limit:
                raise TranscriptionLimitError(
                    f"{name} exceeds its implementation maximum ({hard_limit})"
                )

    @property
    def configuration_digest(self) -> str:
        return stable_id("transcription-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )
