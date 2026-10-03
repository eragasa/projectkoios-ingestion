from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMetadataResponseIdentity,
    OllamaMetadataStage,
    OllamaMultimodalFailure,
)


@dataclass(frozen=True)
class OllamaModelListVerificationResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    CONTRACT_NAME: ClassVar[str] = "ollama-model-list-verification-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    failure: OllamaMultimodalFailure | None
    response_identity: OllamaMetadataResponseIdentity

    def __post_init__(self) -> None:
        if self.failure is not None and not isinstance(
            self.failure, OllamaMultimodalFailure
        ):
            raise TypeError("failure must be OllamaMultimodalFailure or None")
        if not isinstance(
            self.response_identity, OllamaMetadataResponseIdentity
        ):
            raise TypeError(
                "response_identity must be OllamaMetadataResponseIdentity"
            )
        if self.response_identity.stage not in (
            OllamaMetadataStage.PREFLIGHT_TAGS,
            OllamaMetadataStage.POSTFLIGHT_TAGS,
        ):
            raise ValueError("model-list verification requires a tag response")
