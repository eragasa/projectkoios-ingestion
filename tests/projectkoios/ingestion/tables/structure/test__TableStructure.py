"""Ownership and nominal-base checks for TableStructure."""

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.model import TableStructure


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructure.__module__
        == "projectkoios.ingestion.tables.structure.model"
    )
    assert issubclass(TableStructure, AbstractImmutableDataObject)
