from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _request
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaPromptRecord,
)


def test__prompt_record__owns_template_and_version() -> None:
    prompt = _request().prompt

    assert isinstance(prompt, OllamaPromptRecord)
    assert prompt.CONTRACT_NAME == "ollama-multimodal-prompt"
    assert prompt.version == prompt.CONTRACT_VERSION
    assert prompt.text == prompt.TEMPLATE.format(
        prompt_version=prompt.CONTRACT_VERSION,
        manifest=prompt.text.split("Ordered evidence manifest:\n", 1)[1][:-1],
    )


def test__prompt_record__rejects_version_tampering() -> None:
    prompt = _request().prompt

    with pytest.raises(ValueError, match="unsupported prompt version"):
        replace(prompt, version="region-transcription-v2")
