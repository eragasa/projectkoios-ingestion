from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.derivation.cell import (
    TableCellDerivation,
)


def test__table_cell_derivation__is_immutable_owned_state() -> None:
    assert TableCellDerivation.__module__ == (
        "projectkoios.ingestion.tables.structure.derivation.cell"
    )
    assert issubclass(TableCellDerivation, AbstractTableStructureDataObject)
    assert issubclass(TableCellDerivation, AbstractDerivation)
    assert TableCellDerivation.CONTRACT_NAME == "table-cell-derivation"
