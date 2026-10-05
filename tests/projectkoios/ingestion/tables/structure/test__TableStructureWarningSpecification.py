"""Ownership and immutability checks for internal warning specifications."""

from dataclasses import FrozenInstanceError

import pytest
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.warning_specification import (
    TableStructureWarningSpecification,
)


def test__warning_spec_is_frozen_and_owned() -> None:
    warning = TableStructureWarningSpecification("code", "message", (), ())
    assert TableStructureWarningSpecification.__module__ == (
        "projectkoios.ingestion.tables.structure.warning_specification"
    )
    assert issubclass(
        TableStructureWarningSpecification,
        AbstractImmutableDataObject,
    )
    with pytest.raises(FrozenInstanceError):
        warning.code = "changed"  # type: ignore[misc]
