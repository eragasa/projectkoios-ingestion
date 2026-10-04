from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.cell_validation import (
    TableCellValidation,
)


def test__table_cell_validation__is_immutable_owned_state() -> None:
    assert TableCellValidation.__module__ == (
        "projectkoios.ingestion.tables.structure.cell_validation"
    )
    assert issubclass(TableCellValidation, AbstractTableStructureDataObject)
    assert TableCellValidation.CONTRACT_NAME == "table-cell-validation"
