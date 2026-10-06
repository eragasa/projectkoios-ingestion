"""Ingestion-owned action-result base tests."""

import inspect

import pytest
from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


def test__action_result_base__has_immutable_result_roles() -> None:
    assert inspect.isabstract(AbstractDataObjectActionResult)
    assert issubclass(
        AbstractDataObjectActionResult,
        AbstractImmutableDataObject,
    )
    assert issubclass(AbstractDataObjectActionResult, DataObjectActionResult)
    with pytest.raises(TypeError):
        AbstractDataObjectActionResult()
