from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.validation import (
    TableStructureValidation,
)


def test__table_structure_validation__is_immutable_owned_state() -> None:
    assert TableStructureValidation.__module__ == (
        "projectkoios.ingestion.tables.structure.validation"
    )
    assert issubclass(
        TableStructureValidation, AbstractTableStructureDataObject
    )
    assert (
        TableStructureValidation.CONTRACT_NAME == "table-structure-validation"
    )
