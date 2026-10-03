from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.identity import stable_id

from ..processor.region.identity import OllamaMultimodalRegionProcessorIdentity
from ..processor.region.request import OllamaMultimodalRegionProcessingRequest


@dataclass(frozen=True)
class OllamaMultimodalCacheKeyIdentity(AbstractIdentity):
    CONTRACT_NAME: ClassVar[str] = "ollama-multimodal-cache-key"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    cache_key: str
    request_id: str
    processor_identity: OllamaMultimodalRegionProcessorIdentity

    @classmethod
    def create(
        cls,
        *,
        request: OllamaMultimodalRegionProcessingRequest,
        processor_identity: OllamaMultimodalRegionProcessorIdentity,
    ) -> OllamaMultimodalCacheKeyIdentity:
        return cls(
            cache_key=stable_id(
                cls.CONTRACT_NAME,
                cls.CONTRACT_VERSION,
                request.request_id,
                processor_identity,
            ),
            request_id=request.request_id,
            processor_identity=processor_identity,
        )

    def __post_init__(self) -> None:
        if not isinstance(
            self.processor_identity,
            OllamaMultimodalRegionProcessorIdentity,
        ):
            raise TypeError(
                "processor_identity must be "
                "OllamaMultimodalRegionProcessorIdentity"
            )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.request_id,
            self.processor_identity,
        )
        if self.cache_key != expected:
            raise ValueError("multimodal cache-key identity mismatch")
