"""Textbook structure analyzer boundary tests."""

import inspect

import pytest
from projectkoios.ingestion.documents.structure.analyzer import (
    DocumentStructureAnalyzer,
)
from projectkoios.ingestion.textbooks.structure.analyzer.base import (
    TextbookStructureAnalyzer,
)


def test__textbook_structure_analyzer__is_abstract() -> None:
    assert issubclass(TextbookStructureAnalyzer, DocumentStructureAnalyzer)
    assert inspect.isabstract(TextbookStructureAnalyzer)
    with pytest.raises(TypeError):
        TextbookStructureAnalyzer()
