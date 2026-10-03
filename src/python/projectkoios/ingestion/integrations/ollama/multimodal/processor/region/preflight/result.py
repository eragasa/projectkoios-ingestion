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
class OllamaMultimodalPreflightResult(
    AbstractImmutableDataObject,
    DataObjectActionResult,
):
    CONTRACT_NAME: ClassVar[str] = "ollama-multimodal-preflight-result"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    failure: OllamaMultimodalFailure | None
    metadata_responses: tuple[OllamaMetadataResponseIdentity, ...]
    capabilities: frozenset[str]
    observed_version: str | None

    def __post_init__(self) -> None:
        if self.failure is not None and not isinstance(
            self.failure, OllamaMultimodalFailure
        ):
            raise TypeError("failure must be OllamaMultimodalFailure or None")
        if not isinstance(self.metadata_responses, tuple) or any(
            not isinstance(item, OllamaMetadataResponseIdentity)
            for item in self.metadata_responses
        ):
            raise TypeError(
                "metadata_responses must contain metadata identities"
            )
        expected_stages = (
            OllamaMetadataStage.PREFLIGHT_VERSION,
            OllamaMetadataStage.PREFLIGHT_TAGS,
            OllamaMetadataStage.PREFLIGHT_SHOW,
        )
        actual_stages = tuple(item.stage for item in self.metadata_responses)
        if actual_stages != expected_stages[: len(actual_stages)]:
            raise ValueError("preflight metadata stages are not canonical")
        if not isinstance(self.capabilities, frozenset) or any(
            not isinstance(item, str) or not item for item in self.capabilities
        ):
            raise TypeError("capabilities must be a frozenset of names")
        if self.observed_version is not None and (
            not isinstance(self.observed_version, str)
            or not self.observed_version
        ):
            raise ValueError("observed_version must be nonempty or None")
        if self.failure is None and (
            len(self.metadata_responses) != len(expected_stages)
            or self.observed_version is None
        ):
            raise ValueError("successful preflight result is incomplete")
