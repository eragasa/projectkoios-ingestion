from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaRawResponseIdentity,
)


def test__raw_response_identity__owns_its_contract_version() -> None:
    request = _request()
    processor, _ = _processor(request)
    identity = processor.action(request=request).raw_response

    assert isinstance(identity, OllamaRawResponseIdentity)
    assert isinstance(identity, AbstractIdentity)
    assert identity.CONTRACT_NAME == "ollama-raw-response-identity"
    assert identity.CONTRACT_VERSION == "1.0"


def test__raw_response_identity__rejects_digest_tampering() -> None:
    request = _request()
    processor, _ = _processor(request)
    identity = processor.action(request=request).raw_response
    assert identity is not None

    with pytest.raises(ValueError, match="SHA-256"):
        replace(identity, http_body_sha256="bad")
