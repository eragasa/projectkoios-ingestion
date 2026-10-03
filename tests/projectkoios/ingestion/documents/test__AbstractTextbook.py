import inspect

from projectkoios.ingestion import AbstractTextbook as RootAbstractTextbook
from projectkoios.ingestion.documents.base import (
    AbstractDocument,
    AbstractTextbook,
)
from projectkoios.ingestion.documents.extracted import ExtractedTextbook


def test__abstract_textbook__specializes_abstract_document() -> None:
    assert RootAbstractTextbook is AbstractTextbook
    assert issubclass(AbstractTextbook, AbstractDocument)
    assert inspect.isabstract(AbstractTextbook)
    assert issubclass(ExtractedTextbook, AbstractTextbook)
    assert not inspect.isabstract(ExtractedTextbook)
