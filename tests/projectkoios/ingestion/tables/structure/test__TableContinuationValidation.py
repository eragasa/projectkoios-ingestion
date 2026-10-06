from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.validation.continuation import (
    TableContinuationValidation,
)


def test__table_continuation_validation__is_immutable_owned_state() -> None:
    assert TableContinuationValidation.__module__ == (
        "projectkoios.ingestion.tables.structure.validation.continuation"
    )
    assert issubclass(
        TableContinuationValidation, AbstractTableStructureDataObject
    )
    assert issubclass(TableContinuationValidation, AbstractValidation)
    assert (
        TableContinuationValidation.CONTRACT_NAME
        == "table-continuation-validation"
    )
