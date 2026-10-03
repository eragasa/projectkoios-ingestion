from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.base import DataObjectActionResult


def test__preflight_result__is_a_versioned_action_result() -> None:
    request = _request()
    processor, _ = _processor(request)
    result = processor._verify_preflight()

    assert isinstance(result, DataObjectActionResult)
    assert result.CONTRACT_NAME == "ollama-multimodal-preflight-result"
    assert result.CONTRACT_VERSION == "1.0"
    assert result.failure is None


def test__preflight_result__rejects_incomplete_success() -> None:
    request = _request()
    processor, _ = _processor(request)
    result = processor._verify_preflight()

    with pytest.raises(ValueError, match="successful preflight result"):
        replace(result, observed_version=None)
