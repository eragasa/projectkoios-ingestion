"""Textbook structure analyzer boundary tests."""

import inspect

import pytest
from projectkoios.ingestion import TextbookStructureAnalyzer


def test__textbook_structure_analyzer__is_abstract() -> None:
    assert inspect.isabstract(TextbookStructureAnalyzer)
    with pytest.raises(TypeError):
        TextbookStructureAnalyzer()
