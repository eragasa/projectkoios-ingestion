from __future__ import annotations

from projectkoios.ingestion.integrations.ollama.base import (
    OllamaTransportError,
    OllamaTransportFailureKind,
)
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalFailure,
    OllamaMultimodalFailureKind,
)


def test__failure__constructs_transport_failure() -> None:
    failure = OllamaMultimodalFailure.from_transport(
        OllamaTransportError(
            OllamaTransportFailureKind.TIMEOUT,
            "timed out",
        ),
        "chat",
    )

    assert failure.kind is OllamaMultimodalFailureKind.TIMEOUT
    assert failure.code == "ollama.chat.timeout"
    assert failure.retryable is True
