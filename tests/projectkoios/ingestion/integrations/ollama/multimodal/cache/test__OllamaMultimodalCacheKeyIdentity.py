from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.integrations.ollama.multimodal.cache import (
    identity as cache_identity,
)

OllamaMultimodalCacheKeyIdentity = (
    cache_identity.OllamaMultimodalCacheKeyIdentity
)


def test__cache_key_identity__owns_its_contract_version() -> None:
    request = _request()
    processor, _ = _processor(request)
    identity = OllamaMultimodalCacheKeyIdentity.create(
        request=request,
        processor_identity=processor.identity(),
    )

    assert isinstance(identity, AbstractIdentity)
    assert identity.CONTRACT_NAME == "ollama-multimodal-cache-key"
    assert identity.CONTRACT_VERSION == "1.0"
    assert identity.cache_key == (
        "ollama-multimodal-cache-key:sha256:"
        "167fed69d1710b9c87f0c598db0cf82ba3649144c1050f16c9ff5d974726e004"
    )


def test__cache_key_identity__rejects_key_tampering() -> None:
    request = _request()
    processor, _ = _processor(request)
    identity = OllamaMultimodalCacheKeyIdentity.create(
        request=request,
        processor_identity=processor.identity(),
    )

    with pytest.raises(ValueError, match="cache-key identity mismatch"):
        replace(
            identity, cache_key="ollama-multimodal-cache-key:sha256:" + "0" * 64
        )
