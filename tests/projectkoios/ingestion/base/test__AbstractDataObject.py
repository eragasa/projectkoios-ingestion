import inspect

from projectkoios.base import DataObject
from projectkoios.ingestion.base.data_object import AbstractDataObject


def test__abstract_data_object__is_the_ingestion_data_object_root() -> None:
    assert issubclass(AbstractDataObject, DataObject)
    assert inspect.isabstract(AbstractDataObject)
