from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.continuation_validation import (
    TableContinuationValidation,
)


def test__table_continuation_validation__is_immutable_owned_state() -> None:
    assert TableContinuationValidation.__module__ == (
        "projectkoios.ingestion.tables.structure.continuation_validation"
    )
    assert issubclass(
        TableContinuationValidation, AbstractTableStructureDataObject
    )
    assert (
        TableContinuationValidation.CONTRACT_NAME
        == "table-continuation-validation"
    )
