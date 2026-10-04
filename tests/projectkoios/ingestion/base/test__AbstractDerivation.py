from inspect import isabstract

from projectkoios.ingestion.base import (
    AbstractDerivation,
    AbstractImmutableDataObject,
)


def test__abstract_derivation__is_nominal_immutable_base() -> None:
    assert isabstract(AbstractDerivation)
    assert issubclass(AbstractDerivation, AbstractImmutableDataObject)
