import inspect

from projectkoios.ingestion import (
    AbstractDocumentPage as RootAbstractDocumentPage,
)
from projectkoios.ingestion.documents.page.base import AbstractDocumentPage


def test__abstract_document_page__is_the_canonical_page_root() -> None:
    assert RootAbstractDocumentPage is AbstractDocumentPage
    assert inspect.isabstract(AbstractDocumentPage)
