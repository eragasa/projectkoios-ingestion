"""Ownership and nominal-base checks for TableStructure."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.structure import TableStructure


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructure.__module__
        == "projectkoios.ingestion.tables.structure.structure"
    )
    assert issubclass(TableStructure, AbstractImmutableDataObject)
