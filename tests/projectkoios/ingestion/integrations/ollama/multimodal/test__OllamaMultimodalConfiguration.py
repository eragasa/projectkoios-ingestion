import pytest
from conftest import _DIGEST, _MODEL, _VERSION
from projectkoios.ingestion.integrations.ollama.base import (
    OllamaMultimodalConfigurationError,
)
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalConfiguration,
)


def test__configuration__owns_contract_identity() -> None:
    assert (
        OllamaMultimodalConfiguration.CONTRACT_NAME
        == "ollama-multimodal-configuration"
    )
    assert OllamaMultimodalConfiguration.CONTRACT_VERSION == "1"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:11434",
        "http://192.168.1.2:11434",
        "http://example.test:11434",
        "http://user:secret@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
    ],
)
def test__configuration__rejects_nonlocal_or_unsafe_endpoint(
    endpoint: str,
) -> None:
    with pytest.raises(OllamaMultimodalConfigurationError):
        OllamaMultimodalConfiguration(
            endpoint=endpoint,
            model_name=_MODEL,
            expected_model_digest=_DIGEST,
            expected_ollama_version=_VERSION,
        )
