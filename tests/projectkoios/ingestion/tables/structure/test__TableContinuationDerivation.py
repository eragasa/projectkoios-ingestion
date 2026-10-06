from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.derivation.continuation import (
    TableContinuationDerivation,
)


def test__table_continuation_derivation__is_immutable_owned_state() -> None:
    assert TableContinuationDerivation.__module__ == (
        "projectkoios.ingestion.tables.structure.derivation.continuation"
    )
    assert issubclass(
        TableContinuationDerivation, AbstractTableStructureDataObject
    )
    assert issubclass(TableContinuationDerivation, AbstractDerivation)
    assert (
        TableContinuationDerivation.CONTRACT_NAME
        == "table-continuation-derivation"
    )
