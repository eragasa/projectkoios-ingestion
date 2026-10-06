from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.validation.structure import (
    TableStructureValidation,
)


def test__table_structure_validation__is_immutable_owned_state() -> None:
    assert TableStructureValidation.__module__ == (
        "projectkoios.ingestion.tables.structure.validation.structure"
    )
    assert issubclass(
        TableStructureValidation, AbstractTableStructureDataObject
    )
    assert issubclass(TableStructureValidation, AbstractValidation)
    assert (
        TableStructureValidation.CONTRACT_NAME == "table-structure-validation"
    )
