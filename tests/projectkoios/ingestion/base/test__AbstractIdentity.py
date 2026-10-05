import inspect

from projectkoios.ingestion.base.identity import AbstractIdentity
from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject


def test__abstract_identity__specializes_immutable_data_object() -> None:
    assert issubclass(AbstractIdentity, AbstractImmutableDataObject)
    assert inspect.isabstract(AbstractIdentity)
