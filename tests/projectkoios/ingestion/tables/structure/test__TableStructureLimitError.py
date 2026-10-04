"""Ownership and nominal-base checks for TableStructureLimitError."""

from builtins import ValueError

from projectkoios.ingestion.tables.structure.limit_error import (
    TableStructureLimitError,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructureLimitError.__module__
        == "projectkoios.ingestion.tables.structure.limit_error"
    )
    assert issubclass(TableStructureLimitError, ValueError)
