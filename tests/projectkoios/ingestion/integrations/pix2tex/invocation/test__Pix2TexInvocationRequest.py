from __future__ import annotations

import pytest
from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.integrations.pix2tex.invocation.request import (
    Pix2TexInvocationRequest,
)


def test__pix2tex_invocation_request__is_an_action_request() -> None:
    assert issubclass(Pix2TexInvocationRequest, DataObjectActionRequest)
    assert issubclass(Pix2TexInvocationRequest, AbstractImmutableDataObject)


def test__pix2tex_invocation_request__rejects_empty_inventory() -> None:
    with pytest.raises(ValueError, match="requires typed equation assemblies"):
        Pix2TexInvocationRequest(assemblies=())
