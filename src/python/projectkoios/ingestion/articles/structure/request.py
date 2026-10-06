"""Immutable article-structure action request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.articles.structure.configuration import (
    ArticleStructureConfiguration,
)
from projectkoios.ingestion.articles.structure.validation.input import (
    _validate_input,
)
from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import ExtractedDocument


@dataclass(frozen=True, slots=True)
class ArticleStructureRequest(
    ConfigurableDataObjectActionRequest[ArticleStructureConfiguration]
):
    """Bind one document, exact layout evidence, and complete bounds."""

    CONTRACT_NAME: ClassVar[str] = "article-structure-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    document: ExtractedDocument
    layouts: tuple[PageLayoutResult, ...]
    configuration: ArticleStructureConfiguration
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        layouts: tuple[PageLayoutResult, ...],
        configuration: ArticleStructureConfiguration | None = None,
    ) -> ArticleStructureRequest:
        if (
            configuration is not None
            and type(configuration) is not ArticleStructureConfiguration
        ):
            raise TypeError(
                "configuration must be ArticleStructureConfiguration"
            )
        actual_configuration = (
            ArticleStructureConfiguration()
            if configuration is None
            else configuration
        )
        _validate_input(document, layouts, actual_configuration)
        return cls(
            request_id=stable_id(
                cls.CONTRACT_NAME,
                cls.CONTRACT_VERSION,
                document,
                tuple(layout.result_id for layout in layouts),
                actual_configuration.configuration_id,
            ),
            document=document,
            layouts=layouts,
            configuration=actual_configuration,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported article-structure request contract")
        if type(self.configuration) is not ArticleStructureConfiguration:
            raise TypeError(
                "configuration must be ArticleStructureConfiguration"
            )
        _validate_input(self.document, self.layouts, self.configuration)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.document,
            tuple(layout.result_id for layout in self.layouts),
            self.configuration.configuration_id,
        )
        if self.request_id != expected:
            raise ValueError("article-structure request ID is inconsistent")
