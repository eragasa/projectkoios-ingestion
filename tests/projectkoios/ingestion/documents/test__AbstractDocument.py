import inspect

from projectkoios.ingestion import AbstractDocument as RootAbstractDocument
from projectkoios.ingestion.documents.base import AbstractDocument


def test__abstract_document__is_the_canonical_abstract_root() -> None:
    assert RootAbstractDocument is AbstractDocument
    assert inspect.isabstract(AbstractDocument)
