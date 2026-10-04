"""Ownership and nominal-base checks for TableStructureConfiguration."""

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.configuration import (
    TableStructureConfiguration,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructureConfiguration.__module__
        == "projectkoios.ingestion.tables.structure.configuration"
    )
    assert issubclass(TableStructureConfiguration, AbstractImmutableDataObject)
