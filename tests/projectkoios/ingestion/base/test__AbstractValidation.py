from inspect import isabstract

from projectkoios.ingestion.base import (
    AbstractImmutableDataObject,
    AbstractValidation,
)


def test__abstract_validation__is_nominal_immutable_base() -> None:
    assert isabstract(AbstractValidation)
    assert issubclass(AbstractValidation, AbstractImmutableDataObject)
