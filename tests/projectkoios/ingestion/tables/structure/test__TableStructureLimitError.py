"""Ownership and nominal-base checks for TableStructureLimitError."""

from builtins import ValueError

from projectkoios.ingestion.tables.structure.limits.error import (
    TableStructureLimitError,
)


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableStructureLimitError.__module__
        == "projectkoios.ingestion.tables.structure.limits.error"
    )
    assert issubclass(TableStructureLimitError, ValueError)
