from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _request
from projectkoios.ingestion.base import AbstractIdentity


def test__selection_identity__owns_its_contract_version() -> None:
    identity = _request().selections[0].identity

    assert isinstance(identity, AbstractIdentity)
    assert identity.CONTRACT_NAME == "ollama-multimodal-selection"
    assert identity.CONTRACT_VERSION == "1.0"
    assert identity.selection_id == (
        "ollama-multimodal-selection:sha256:"
        "43d8faed1e5513dad0ee96e3bb177a1e8ced60176f1cfec504de114c8ca8ee70"
    )


def test__selection_identity__rejects_provenance_tampering() -> None:
    identity = _request().selections[0].identity

    with pytest.raises(ValueError, match="selection identity mismatch"):
        replace(identity, region_id="changed")


def test__selection_identity__rejects_blob_hash_disagreement() -> None:
    identity = _request().selections[0].identity

    with pytest.raises(ValueError, match="blob and source hash disagree"):
        replace(identity, source_blob_id=f"blob:sha256:{'b' * 64}")
