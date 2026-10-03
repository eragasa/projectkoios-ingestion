from __future__ import annotations

import inspect

from projectkoios.ingestion.base import AbstractImmutableDataObject
from projectkoios.ingestion.equations.base import AbstractEquation


def test__abstract_equation__is_an_immutable_abstract_data_object() -> None:
    assert inspect.isabstract(AbstractEquation)
    assert issubclass(AbstractEquation, AbstractImmutableDataObject)
