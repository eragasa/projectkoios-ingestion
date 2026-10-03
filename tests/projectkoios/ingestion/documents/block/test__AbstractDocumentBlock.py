import inspect

from projectkoios.ingestion import (
    AbstractDocumentBlock as RootAbstractDocumentBlock,
)
from projectkoios.ingestion.documents.block.base import AbstractDocumentBlock


def test__abstract_document_block__is_the_canonical_block_root() -> None:
    assert RootAbstractDocumentBlock is AbstractDocumentBlock
    assert inspect.isabstract(AbstractDocumentBlock)
