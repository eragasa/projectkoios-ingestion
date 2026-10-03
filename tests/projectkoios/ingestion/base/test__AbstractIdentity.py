import inspect

from projectkoios.ingestion.base import (
    AbstractIdentity,
    AbstractImmutableDataObject,
)


def test__abstract_identity__specializes_immutable_data_object() -> None:
    assert issubclass(AbstractIdentity, AbstractImmutableDataObject)
    assert inspect.isabstract(AbstractIdentity)
