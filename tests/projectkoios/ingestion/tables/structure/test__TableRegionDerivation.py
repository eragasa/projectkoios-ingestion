from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.region_derivation import (
    TableRegionDerivation,
)


def test__table_region_derivation__is_immutable_owned_state() -> None:
    assert TableRegionDerivation.__module__ == (
        "projectkoios.ingestion.tables.structure.region_derivation"
    )
    assert issubclass(TableRegionDerivation, AbstractTableStructureDataObject)
    assert TableRegionDerivation.CONTRACT_NAME == "table-region-derivation"
