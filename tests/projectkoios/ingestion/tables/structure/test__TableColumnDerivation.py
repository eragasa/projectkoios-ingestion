from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.column_derivation import (
    TableColumnDerivation,
)


def test__table_column_derivation__is_immutable_owned_state() -> None:
    assert TableColumnDerivation.__module__ == (
        "projectkoios.ingestion.tables.structure.column_derivation"
    )
    assert issubclass(TableColumnDerivation, AbstractTableStructureDataObject)
    assert issubclass(TableColumnDerivation, AbstractDerivation)
    assert TableColumnDerivation.CONTRACT_NAME == "table-column-derivation"
