from inspect import isabstract

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.base.validation import AbstractValidation


def test__abstract_validation__is_nominal_immutable_base() -> None:
    assert isabstract(AbstractValidation)
    assert issubclass(AbstractValidation, AbstractImmutableDataObject)
