from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.row_validation import (
    TableRowValidation,
)


def test__table_row_validation__is_immutable_owned_state() -> None:
    assert TableRowValidation.__module__ == (
        "projectkoios.ingestion.tables.structure.row_validation"
    )
    assert issubclass(TableRowValidation, AbstractTableStructureDataObject)
    assert issubclass(TableRowValidation, AbstractValidation)
    assert TableRowValidation.CONTRACT_NAME == "table-row-validation"
