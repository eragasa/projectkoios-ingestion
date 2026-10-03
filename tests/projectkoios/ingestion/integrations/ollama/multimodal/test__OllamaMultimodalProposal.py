from __future__ import annotations

from dataclasses import replace

import pytest
from conftest import _processor, _request
from projectkoios.ingestion.integrations.ollama.multimodal.base import (
    OllamaMultimodalDeterminism,
    OllamaMultimodalEvidenceStatus,
    OllamaMultimodalProposal,
)


def test__proposal__remains_unreviewed_and_nondeterministic() -> None:
    request = _request()
    processor, _ = _processor(request)
    proposal = processor.action(request=request).selection_results[0].proposal

    assert isinstance(proposal, OllamaMultimodalProposal)
    assert (
        proposal.status is OllamaMultimodalEvidenceStatus.AUTOMATED_UNREVIEWED
    )
    assert proposal.determinism is OllamaMultimodalDeterminism.NONDETERMINISTIC


def test__proposal__rejects_digest_tampering() -> None:
    request = _request()
    processor, _ = _processor(request)
    proposal = processor.action(request=request).selection_results[0].proposal
    assert proposal is not None

    with pytest.raises(ValueError, match="digest mismatch"):
        replace(proposal, text_sha256="0" * 64)
