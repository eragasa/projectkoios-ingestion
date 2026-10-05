"""Ownership and nominal-base checks for TableColumn."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.column import TableColumn


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableColumn.__module__
        == "projectkoios.ingestion.tables.structure.column"
    )
    assert issubclass(TableColumn, AbstractImmutableDataObject)
