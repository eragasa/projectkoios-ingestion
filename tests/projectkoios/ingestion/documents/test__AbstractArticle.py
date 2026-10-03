import inspect

from projectkoios.ingestion import AbstractArticle as RootAbstractArticle
from projectkoios.ingestion.documents.base import (
    AbstractArticle,
    AbstractDocument,
)
from projectkoios.ingestion.documents.extracted import ExtractedArticle


def test__abstract_article__specializes_abstract_document() -> None:
    assert RootAbstractArticle is AbstractArticle
    assert issubclass(AbstractArticle, AbstractDocument)
    assert inspect.isabstract(AbstractArticle)
    assert issubclass(ExtractedArticle, AbstractArticle)
    assert not inspect.isabstract(ExtractedArticle)
