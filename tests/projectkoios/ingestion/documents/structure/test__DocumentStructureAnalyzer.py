"""Shared document-structure analyzer boundary tests."""

import inspect

import pytest
from projectkoios.ingestion.documents.structure.analyzer import (
    DocumentStructureAnalyzer,
)


def test__document_structure_analyzer__is_nominal_and_abstract() -> None:
    assert inspect.isabstract(DocumentStructureAnalyzer)
    with pytest.raises(TypeError):
        DocumentStructureAnalyzer()
