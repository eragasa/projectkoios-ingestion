"""Identified request/actionizer/result boundary for layout analysis."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.contracts import (
    DeterministicLayoutProcessor,
    LayoutConfiguration,
    PageLayoutResult,
)
from projectkoios.ingestion.models import ExtractedDocument

LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION = "1.0"
LAYOUT_ANALYSIS_ACTIONIZER_NAME = "deterministic-layout-analysis-actionizer"
LAYOUT_ANALYSIS_ACTIONIZER_VERSION = "1"


def _request_id(
    *,
    document: ExtractedDocument,
    configuration: LayoutConfiguration,
) -> str:
    return stable_id(
        "layout-analysis-request",
        document,
        configuration.configuration_digest,
        LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION,
    )


@dataclass(frozen=True, slots=True)
class LayoutAnalysisRequest:
    """Complete immutable intent for deterministic document layout analysis."""

    request_id: str
    document: ExtractedDocument
    configuration: LayoutConfiguration
    contract_version: str = LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        configuration: LayoutConfiguration,
    ) -> LayoutAnalysisRequest:
        if not isinstance(document, ExtractedDocument):
            raise TypeError("document must be ExtractedDocument")
        if not isinstance(configuration, LayoutConfiguration):
            raise TypeError("configuration must be LayoutConfiguration")
        return cls(
            request_id=_request_id(
                document=document,
                configuration=configuration,
            ),
            document=document,
            configuration=configuration,
        )

    def __post_init__(self) -> None:
        if self.contract_version != LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported layout-analysis request contract")
        if not isinstance(self.document, ExtractedDocument):
            raise TypeError("document must be ExtractedDocument")
        if not isinstance(self.configuration, LayoutConfiguration):
            raise TypeError("configuration must be LayoutConfiguration")
        expected = _request_id(
            document=self.document,
            configuration=self.configuration,
        )
        if self.request_id != expected:
            raise ValueError("layout-analysis request ID is inconsistent")


@dataclass(frozen=True, slots=True)
class LayoutAnalysisResult:
    """Identified deterministic outcome for one exact layout request."""

    result_id: str
    request_id: str
    page_results: tuple[PageLayoutResult, ...]
    actionizer_name: str
    actionizer_version: str
    configuration_digest: str
    contract_version: str = LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        request: LayoutAnalysisRequest,
        page_results: tuple[PageLayoutResult, ...],
        actionizer_name: str,
        actionizer_version: str,
    ) -> LayoutAnalysisResult:
        if not isinstance(request, LayoutAnalysisRequest):
            raise TypeError("request must be LayoutAnalysisRequest")
        if not isinstance(page_results, tuple) or any(
            not isinstance(result, PageLayoutResult) for result in page_results
        ):
            raise TypeError("page_results must contain PageLayoutResult values")
        expected_indices = tuple(
            page.page_index for page in request.document.pages
        )
        actual_indices = tuple(result.page_index for result in page_results)
        if actual_indices != expected_indices:
            raise ValueError("layout results do not match request page order")
        result_id = stable_id(
            "layout-analysis-action-result",
            request.request_id,
            tuple(result.result_id for result in page_results),
            actionizer_name,
            actionizer_version,
            request.configuration.configuration_digest,
            LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION,
        )
        return cls(
            result_id=result_id,
            request_id=request.request_id,
            page_results=page_results,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
            configuration_digest=request.configuration.configuration_digest,
        )

    def __post_init__(self) -> None:
        if self.contract_version != LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION:
            raise ValueError("unsupported layout-analysis result contract")
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if not isinstance(self.page_results, tuple) or any(
            not isinstance(result, PageLayoutResult)
            for result in self.page_results
        ):
            raise TypeError("page_results must contain PageLayoutResult values")
        result_ids = tuple(result.result_id for result in self.page_results)
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("page_results must have unique identities")
        if any(
            result.configuration_digest != self.configuration_digest
            for result in self.page_results
        ):
            raise ValueError("layout result configuration identities disagree")
        if not self.actionizer_name or not self.actionizer_version:
            raise ValueError("actionizer identity must be complete")
        expected = stable_id(
            "layout-analysis-action-result",
            self.request_id,
            result_ids,
            self.actionizer_name,
            self.actionizer_version,
            self.configuration_digest,
            self.contract_version,
        )
        if self.result_id != expected:
            raise ValueError("layout-analysis result ID is inconsistent")


class LayoutAnalysisActionizer:
    """Execute deterministic layout analysis for one identified request."""

    __slots__ = ()

    actionizer_name = LAYOUT_ANALYSIS_ACTIONIZER_NAME
    actionizer_version = LAYOUT_ANALYSIS_ACTIONIZER_VERSION

    def execute(
        self, *, request: LayoutAnalysisRequest
    ) -> LayoutAnalysisResult:
        if not isinstance(request, LayoutAnalysisRequest):
            raise TypeError("request must be LayoutAnalysisRequest")
        processor = DeterministicLayoutProcessor(
            configuration=request.configuration
        )
        page_results = processor.analyze(document=request.document)
        return LayoutAnalysisResult.create(
            request=request,
            page_results=page_results,
            actionizer_name=self.actionizer_name,
            actionizer_version=self.actionizer_version,
        )


__all__ = [
    "LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION",
    "LAYOUT_ANALYSIS_ACTIONIZER_NAME",
    "LAYOUT_ANALYSIS_ACTIONIZER_VERSION",
    "LayoutAnalysisActionizer",
    "LayoutAnalysisRequest",
    "LayoutAnalysisResult",
]
