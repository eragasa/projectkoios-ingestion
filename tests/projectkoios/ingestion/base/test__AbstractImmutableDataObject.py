import inspect

from projectkoios.ingestion.base import (
    AbstractDataObject,
    AbstractImmutableDataObject,
)


def test__abstract_immutable_data_object__specializes_data_object() -> None:
    assert issubclass(AbstractImmutableDataObject, AbstractDataObject)
    assert inspect.isabstract(AbstractImmutableDataObject)
