from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.integrations.ollama.base import (
    OLLAMA_BACKEND_NAME,
    OllamaRequestOptions,
)
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OLLAMA_REQUIRED_CAPABILITIES,
    OllamaMultimodalConfiguration,
    OllamaMultimodalDeterminism,
    OllamaPromptRecord,
)
from projectkoios.ingestion.integrations.ollama.transport.http import (
    normalize_ollama_endpoint,
)


@dataclass(frozen=True)
class OllamaMultimodalRegionProcessorIdentity(AbstractIdentity):
    CONTRACT_NAME: ClassVar[str] = "ollama-multimodal-region-processor-identity"
    CONTRACT_VERSION: ClassVar[str] = "1.0"
    PROCESSOR_NAME: ClassVar[str] = "ollama-multimodal-region-processor"
    PROCESSOR_VERSION: ClassVar[str] = "1"
    RESPONSE_SCHEMA_VERSION: ClassVar[int] = 1

    processor_name: str
    processor_version: str
    backend_name: str
    expected_backend_version: str
    endpoint: str
    model_name: str
    expected_model_digest: str
    required_capabilities: tuple[str, ...]
    prompt_version: str
    prompt_template_sha256: str
    response_schema_version: int
    request_options: OllamaRequestOptions
    configuration: OllamaMultimodalConfiguration
    configuration_digest: str
    determinism: OllamaMultimodalDeterminism

    def __post_init__(self) -> None:
        if (
            self.processor_name != self.PROCESSOR_NAME
            or self.processor_version != self.PROCESSOR_VERSION
            or self.backend_name != OLLAMA_BACKEND_NAME
        ):
            raise ValueError("unsupported processor identity")
        if self.endpoint != normalize_ollama_endpoint(self.endpoint):
            raise ValueError("processor endpoint is not normalized")
        if self.required_capabilities != OLLAMA_REQUIRED_CAPABILITIES:
            raise ValueError("processor capabilities are unsupported")
        if (
            self.prompt_version != OllamaPromptRecord.CONTRACT_VERSION
            or self.prompt_template_sha256
            != OllamaPromptRecord._prompt_template_sha256()
            or self.response_schema_version != self.RESPONSE_SCHEMA_VERSION
        ):
            raise ValueError(
                "processor prompt or schema identity is unsupported"
            )
        if not isinstance(self.request_options, OllamaRequestOptions):
            raise TypeError("request_options must be OllamaRequestOptions")
        if not isinstance(self.configuration, OllamaMultimodalConfiguration):
            raise TypeError(
                "configuration must be OllamaMultimodalConfiguration"
            )
        if (
            self.endpoint != self.configuration.endpoint
            or self.model_name != self.configuration.model_name
            or self.expected_model_digest
            != self.configuration.expected_model_digest
            or self.expected_backend_version
            != self.configuration.expected_ollama_version
            or self.request_options != self.configuration.options
            or self.configuration_digest
            != self.configuration.configuration_digest
        ):
            raise ValueError("processor identity and configuration disagree")
        if self.determinism is not OllamaMultimodalDeterminism.NONDETERMINISTIC:
            raise ValueError("processor identity must be nondeterministic")
