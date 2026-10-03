from __future__ import annotations

import pytest
from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.integrations.pix2tex.invocation.output import (
    Pix2TexInvocationOutput,
)
from projectkoios.ingestion.integrations.pix2tex.invocation.result import (
    Pix2TexInvocationResult,
)


def test__pix2tex_invocation_result__is_an_immutable_action_result() -> None:
    result = Pix2TexInvocationResult(
        diagnostic=b"",
        outputs=(),
    )

    assert isinstance(result, DataObjectActionResult)
    assert isinstance(result, AbstractImmutableDataObject)


def test__pix2tex_invocation_result__rejects_duplicate_outputs() -> None:
    output = Pix2TexInvocationOutput(
        assembly_id="equation-assembly:sha256:" + "a" * 64,
        latex=r"E = mc^2",
    )

    with pytest.raises(ValueError, match="outputs must be unique"):
        Pix2TexInvocationResult(
            diagnostic=b"",
            outputs=(output, output),
        )
