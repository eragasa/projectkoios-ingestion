from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)


def test__table_structure_base__is_ingestion_owned_and_immutable() -> None:
    assert AbstractTableStructureDataObject.__module__ == (
        "projectkoios.ingestion.tables.structure.base"
    )
    assert issubclass(
        AbstractTableStructureDataObject, AbstractImmutableDataObject
    )
