"""Ownership and nominal-base checks for TableStructureResult."""

from projectkoios.base import DataObjectActionResult
from projectkoios.ingestion.tables.structure.result import TableStructureResult


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructureResult.__module__
        == "projectkoios.ingestion.tables.structure.result"
    )
    assert issubclass(TableStructureResult, DataObjectActionResult)
