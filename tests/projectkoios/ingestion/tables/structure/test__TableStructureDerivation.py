from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.derivation import (
    TableStructureDerivation,
)


def test__table_structure_derivation__is_immutable_owned_state() -> None:
    assert TableStructureDerivation.__module__ == (
        "projectkoios.ingestion.tables.structure.derivation"
    )
    assert issubclass(
        TableStructureDerivation, AbstractTableStructureDataObject
    )
    assert (
        TableStructureDerivation.CONTRACT_NAME == "table-structure-derivation"
    )
