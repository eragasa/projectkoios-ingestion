from inspect import isabstract

from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


def test__abstract_derivation__is_nominal_immutable_base() -> None:
    assert isabstract(AbstractDerivation)
    assert issubclass(AbstractDerivation, AbstractImmutableDataObject)
