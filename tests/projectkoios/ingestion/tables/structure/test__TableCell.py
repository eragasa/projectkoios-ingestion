"""Ownership and nominal-base checks for TableCell."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.cell import TableCell


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableCell.__module__ == "projectkoios.ingestion.tables.structure.cell"
    )
    assert issubclass(TableCell, AbstractImmutableDataObject)
