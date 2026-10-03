from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    _HARD_MAX_MODEL_NAME_BYTES,
    OllamaMultimodalConfiguration,
)


@dataclass(frozen=True)
class OllamaModelDescriptor(AbstractImmutableDataObject):
    CONTRACT_NAME: ClassVar[str] = "ollama-model-descriptor"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    model_name: str
    model_digest: str

    def __post_init__(self) -> None:
        OllamaMultimodalConfiguration._bounded_nonempty_utf8(
            "model_name",
            self.model_name,
            _HARD_MAX_MODEL_NAME_BYTES,
        )
        if any(character.isspace() for character in self.model_name):
            raise ValueError("model_name cannot contain whitespace")
        normalized_digest = (
            OllamaMultimodalConfiguration._validate_model_digest(
                self.model_digest
            )
        )
        if self.model_digest != normalized_digest:
            raise ValueError("model_digest must use its canonical bare form")
