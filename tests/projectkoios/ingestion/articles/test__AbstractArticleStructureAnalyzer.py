"""Article structure analyzer boundary tests."""

import inspect

import pytest
from projectkoios.ingestion import (
    ArticleStructureAnalyzer,
    DeterministicArticleStructureAnalyzer,
)


def test__article_structure_analyzer__is_abstract() -> None:
    assert inspect.isabstract(ArticleStructureAnalyzer)
    with pytest.raises(TypeError):
        ArticleStructureAnalyzer()


def test__deterministic_analyzer__inherits_nominal_boundary() -> None:
    assert issubclass(
        DeterministicArticleStructureAnalyzer,
        ArticleStructureAnalyzer,
    )
