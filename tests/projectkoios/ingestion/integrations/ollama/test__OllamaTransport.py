"""Nominal Ollama transport boundary tests."""

import inspect

import pytest
from projectkoios.ingestion.integrations.ollama.base import OllamaTransport
from projectkoios.ingestion.integrations.ollama.transport.http import (
    LoopbackOllamaHttpTransport,
)


def test__ollama_transport__is_abstract() -> None:
    assert inspect.isabstract(OllamaTransport)
    with pytest.raises(TypeError):
        OllamaTransport()


def test__loopback_transport__inherits_nominal_boundary() -> None:
    assert issubclass(LoopbackOllamaHttpTransport, OllamaTransport)
    assert not inspect.isabstract(LoopbackOllamaHttpTransport)
