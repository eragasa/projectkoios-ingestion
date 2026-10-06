"""Article structure analyzer boundary tests."""

import inspect

import pytest
from projectkoios.ingestion.articles.structure.analyzer.base import (
    ArticleStructureAnalyzer,
)
from projectkoios.ingestion.articles.structure.analyzer.deterministic import (
    DeterministicArticleStructureAnalyzer,
)
from projectkoios.ingestion.documents.structure.analyzer import (
    DocumentStructureAnalyzer,
)


def test__article_structure_analyzer__is_abstract() -> None:
    assert issubclass(ArticleStructureAnalyzer, DocumentStructureAnalyzer)
    assert inspect.isabstract(ArticleStructureAnalyzer)
    with pytest.raises(TypeError):
        ArticleStructureAnalyzer()


def test__deterministic_analyzer__inherits_nominal_boundary() -> None:
    assert issubclass(
        DeterministicArticleStructureAnalyzer,
        ArticleStructureAnalyzer,
    )
