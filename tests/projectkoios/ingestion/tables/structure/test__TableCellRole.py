"""Ownership and nominal-base checks for TableCellRole."""

from enum import StrEnum

from projectkoios.ingestion.tables.structure.role.cell import TableCellRole


def test__owned_module_and_nominal_base() -> None:
    assert (
        TableCellRole.__module__
        == "projectkoios.ingestion.tables.structure.role.cell"
    )
    assert issubclass(TableCellRole, StrEnum)
