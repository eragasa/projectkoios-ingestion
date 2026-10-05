"""Ownership and nominal-base checks for TableRow."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.row import TableRow


def test__owned_module_and_nominal_base() -> None:
    assert TableRow.__module__ == "projectkoios.ingestion.tables.structure.row"
    assert issubclass(TableRow, AbstractImmutableDataObject)
