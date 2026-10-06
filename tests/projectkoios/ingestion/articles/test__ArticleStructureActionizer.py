"""Article-structure request/actionizer/result role tests."""

import pytest
from projectkoios.ingestion.articles.structure.actionizer import (
    DeterministicArticleStructureActionizer,
)
from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.request import (
    ArticleStructureRequest,
)
from projectkoios.ingestion.base.actionizer.configurable import (
    ConfigurableDataObjectActionizer,
)
from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.structure import StructureAnalysis


def test__article_structure__uses_ingestion_base_action_roles() -> None:
    assert issubclass(
        ArticleStructureConfiguration,
        AbstractActionConfiguration,
    )
    assert issubclass(
        ArticleStructureRequest,
        ConfigurableDataObjectActionRequest,
    )
    assert issubclass(
        DeterministicArticleStructureActionizer,
        ConfigurableDataObjectActionizer,
    )
    assert issubclass(StructureAnalysis, AbstractDataObjectActionResult)
    actionizer = DeterministicArticleStructureActionizer()
    assert not hasattr(actionizer, "configuration")
    assert not hasattr(actionizer, "analyze")
    assert not hasattr(actionizer, "analyze_with_layout")


def test__article_structure_actionizer__rejects_another_request_role() -> None:
    with pytest.raises(TypeError, match="ArticleStructureRequest"):
        DeterministicArticleStructureActionizer().action(  # type: ignore[arg-type]
            request=object()
        )
