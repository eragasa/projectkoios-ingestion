from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.materialization import (
    TableStructureMaterialization,
)


def test__table_structure_materialization__is_immutable_owned_state() -> None:
    assert TableStructureMaterialization.__module__ == (
        "projectkoios.ingestion.tables.structure.materialization"
    )
    assert issubclass(
        TableStructureMaterialization, AbstractTableStructureDataObject
    )
    assert (
        TableStructureMaterialization.CONTRACT_NAME
        == "table-structure-materialization"
    )
