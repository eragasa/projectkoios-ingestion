from __future__ import annotations

import pytest
from conftest import _DIGEST, _MODEL
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.integrations.ollama.multimodal.processor.region.model_list.model import (  # noqa: E501
    OllamaModelDescriptor,
)


def test__model_descriptor__is_a_versioned_value_object() -> None:
    descriptor = OllamaModelDescriptor(
        model_name=_MODEL,
        model_digest=_DIGEST,
    )

    assert isinstance(descriptor, AbstractImmutableDataObject)
    assert descriptor.CONTRACT_NAME == "ollama-model-descriptor"
    assert descriptor.CONTRACT_VERSION == "1.0"


def test__model_descriptor__rejects_noncanonical_digest() -> None:
    with pytest.raises(ValueError, match="canonical bare form"):
        OllamaModelDescriptor(
            model_name=_MODEL,
            model_digest=f"sha256:{_DIGEST}",
        )
