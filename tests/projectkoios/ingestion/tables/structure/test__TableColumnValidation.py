from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.validation.column import (
    TableColumnValidation,
)


def test__table_column_validation__is_immutable_owned_state() -> None:
    assert TableColumnValidation.__module__ == (
        "projectkoios.ingestion.tables.structure.validation.column"
    )
    assert issubclass(TableColumnValidation, AbstractTableStructureDataObject)
    assert issubclass(TableColumnValidation, AbstractValidation)
    assert TableColumnValidation.CONTRACT_NAME == "table-column-validation"
