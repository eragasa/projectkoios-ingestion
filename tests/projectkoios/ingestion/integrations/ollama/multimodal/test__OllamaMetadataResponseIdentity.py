from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.ingestion.base.identity import AbstractIdentity


def test__metadata_response_identity__is_an_abstract_identity() -> None:
    request = _request()
    processor, _ = _processor(request)
    identity = processor.action(request=request).metadata_responses[0]

    assert isinstance(identity, AbstractIdentity)
    assert identity.CONTRACT_NAME == "ollama-metadata-response-identity"
    assert identity.CONTRACT_VERSION == "1.0"


def test__metadata_response_identity__rejects_stage_path_tampering() -> None:
    request = _request()
    processor, _ = _processor(request)
    identity = processor.action(request=request).metadata_responses[0]

    with pytest.raises(ValueError, match="stage and path"):
        replace(identity, path="/api/tags")
