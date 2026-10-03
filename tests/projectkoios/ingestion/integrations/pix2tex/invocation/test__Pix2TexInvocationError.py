from __future__ import annotations

import pytest
from projectkoios.ingestion.integrations.pix2tex.invocation.error import (
    Pix2TexInvocationError,
)


def test__pix2tex_invocation_error__requires_nonzero_exit() -> None:
    error = Pix2TexInvocationError(
        exit_code=7,
        diagnostic=b"bounded failure",
    )

    assert error.exit_code == 7
    assert error.diagnostic == b"bounded failure"
    with pytest.raises(ValueError, match="requires nonzero exit"):
        Pix2TexInvocationError(exit_code=0, diagnostic=b"")
