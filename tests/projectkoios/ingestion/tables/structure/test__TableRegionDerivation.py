from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.tables.structure.base import (
    AbstractTableStructureDataObject,
)
from projectkoios.ingestion.tables.structure.derivation.region import (
    TableRegionDerivation,
)


def test__table_region_derivation__is_immutable_owned_state() -> None:
    assert TableRegionDerivation.__module__ == (
        "projectkoios.ingestion.tables.structure.derivation.region"
    )
    assert issubclass(TableRegionDerivation, AbstractTableStructureDataObject)
    assert issubclass(TableRegionDerivation, AbstractDerivation)
    assert TableRegionDerivation.CONTRACT_NAME == "table-region-derivation"
