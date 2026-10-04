from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

OLLAMA_BACKEND_NAME = "ollama"


class OllamaMultimodalConfigurationError(ValueError):
    """Raised when local adapter configuration is unsafe or invalid."""


class OllamaTransportFailureKind(StrEnum):
    TIMEOUT = "timeout"
    RESPONSE_LIMIT = "response_limit"
    NETWORK = "network"
    PROTOCOL = "protocol"


class OllamaTransportError(RuntimeError):
    """Bounded transport failure safe for conversion into a result."""

    def __init__(
        self,
        kind: OllamaTransportFailureKind,
        message: str,
    ) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class OllamaHttpResponse:
    status_code: int
    content_type: str
    body: bytes

    def __post_init__(self) -> None:
        if (
            isinstance(self.status_code, bool)
            or not isinstance(self.status_code, int)
            or not 100 <= self.status_code <= 599
        ):
            raise ValueError("status_code must be an HTTP status integer")
        if not isinstance(self.content_type, str):
            raise TypeError("content_type must be a string")
        if not isinstance(self.body, bytes):
            raise TypeError("body must be immutable bytes")


class OllamaTransport(ABC):
    """Nominal bounded request boundary for Ollama transports."""

    __slots__ = ()

    @abstractmethod
    def request(
        self,
        *,
        endpoint: str,
        method: str,
        path: str,
        body: bytes | None,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_response_bytes: int,
    ) -> OllamaHttpResponse: ...


@dataclass(frozen=True)
class OllamaRequestOptions:
    temperature: float = 0.0
    seed: int = 0
    context_tokens: int = 8_192
    output_tokens: int = 2_048
    keep_alive: str = "0"

    def __post_init__(self) -> None:
        if isinstance(self.temperature, bool) or not isinstance(
            self.temperature, int | float
        ):
            raise OllamaMultimodalConfigurationError(
                "temperature must be numeric"
            )
        if not 0.0 <= float(self.temperature) <= 2.0:
            raise OllamaMultimodalConfigurationError(
                "temperature must be between 0 and 2"
            )
        for name, value, maximum in (
            ("seed", self.seed, 2**63 - 1),
            ("context_tokens", self.context_tokens, 1_000_000),
            ("output_tokens", self.output_tokens, 100_000),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < (0 if name == "seed" else 1)
                or value > maximum
            ):
                raise OllamaMultimodalConfigurationError(
                    f"{name} is outside its supported bound"
                )
        if self.keep_alive != "0":
            raise OllamaMultimodalConfigurationError(
                "keep_alive must be '0' for the bounded adapter"
            )

    def as_ollama_json(self) -> dict[str, int | float]:
        return {
            "temperature": float(self.temperature),
            "seed": self.seed,
            "num_ctx": self.context_tokens,
            "num_predict": self.output_tokens,
        }
