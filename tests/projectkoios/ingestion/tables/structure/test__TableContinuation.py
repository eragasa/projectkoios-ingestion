"""Ownership and nominal-base checks for TableContinuation."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.continuation import (
    TableContinuation,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableContinuation.__module__
        == "projectkoios.ingestion.tables.structure.continuation"
    )
    assert issubclass(TableContinuation, AbstractImmutableDataObject)
