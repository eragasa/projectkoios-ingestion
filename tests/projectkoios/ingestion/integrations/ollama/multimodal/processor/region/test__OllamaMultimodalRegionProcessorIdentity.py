from dataclasses import replace

import pytest
from conftest import _DIGEST, _processor, _request
from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.integrations.ollama.base import OllamaRequestOptions


def test__processor_identity__is_an_abstract_identity() -> None:
    processor, _ = _processor(_request())

    identity = processor.identity()
    assert isinstance(identity, AbstractIdentity)
    assert identity.CONTRACT_VERSION == "1.0"
    assert identity.processor_name == identity.PROCESSOR_NAME
    assert identity.processor_version == identity.PROCESSOR_VERSION
    assert identity.response_schema_version == identity.RESPONSE_SCHEMA_VERSION


def test__processor_identity__covers_configuration() -> None:
    request = _request()
    processor, _ = _processor(request)
    changed_model, _ = _processor(request, digest="b" * 64)
    changed_options, _ = _processor(
        request,
        options=OllamaRequestOptions(seed=1),
    )

    identity = processor.identity()
    assert identity != changed_model.identity()
    assert identity != changed_options.identity()
    assert identity.expected_model_digest == _DIGEST
    assert identity.endpoint == "http://127.0.0.1:11434"
    assert identity.required_capabilities == ("vision",)


def test__processor_identity__rejects_configuration_tampering() -> None:
    processor, _ = _processor(_request())

    with pytest.raises(ValueError, match="configuration"):
        replace(processor.identity(), endpoint="http://localhost:11434")
