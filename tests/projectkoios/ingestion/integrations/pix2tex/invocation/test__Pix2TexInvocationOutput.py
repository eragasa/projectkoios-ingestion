from __future__ import annotations

import pytest
from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.integrations.pix2tex.invocation.output import (
    Pix2TexInvocationOutput,
)


def test__pix2tex_invocation_output__requires_identity_and_latex() -> None:
    output = Pix2TexInvocationOutput(
        assembly_id="equation-assembly:sha256:" + "a" * 64,
        latex=r"E = mc^2",
    )

    assert isinstance(output, AbstractImmutableDataObject)
    assert output.latex == r"E = mc^2"
    with pytest.raises(ValueError, match="incomplete"):
        Pix2TexInvocationOutput(assembly_id=output.assembly_id, latex=" ")
