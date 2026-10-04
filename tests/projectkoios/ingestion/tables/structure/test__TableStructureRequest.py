"""Ownership and nominal-base checks for TableStructureRequest."""

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.tables.structure.request import (
    TableStructureRequest,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructureRequest.__module__
        == "projectkoios.ingestion.tables.structure.request"
    )
    assert issubclass(TableStructureRequest, DataObjectActionRequest)
