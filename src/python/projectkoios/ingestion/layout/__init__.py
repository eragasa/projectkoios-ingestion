"""Deterministic page-layout domain API."""

from projectkoios.ingestion.layout.actionizer import (
    LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION,
    LAYOUT_ANALYSIS_ACTIONIZER_NAME,
    LAYOUT_ANALYSIS_ACTIONIZER_VERSION,
    LayoutAnalysisRequest,
    LayoutAnalysisResult,
)
from projectkoios.ingestion.layout.contracts import (
    LAYOUT_CONTRACT_VERSION,
    DeterministicLayoutProcessor,
    LayoutAnalysisLimitError,
    LayoutBlockReference,
    LayoutConfiguration,
    LayoutExclusion,
    LayoutGroupHypothesis,
    LayoutGroupKind,
    LayoutPageKind,
    PageLayoutProcessor,
    PageLayoutResult,
)

__all__ = [
    "LAYOUT_ANALYSIS_ACTION_CONTRACT_VERSION",
    "LAYOUT_ANALYSIS_ACTIONIZER_NAME",
    "LAYOUT_ANALYSIS_ACTIONIZER_VERSION",
    "LAYOUT_CONTRACT_VERSION",
    "DeterministicLayoutProcessor",
    "LayoutAnalysisLimitError",
    "LayoutAnalysisRequest",
    "LayoutAnalysisResult",
    "LayoutBlockReference",
    "LayoutConfiguration",
    "LayoutExclusion",
    "LayoutGroupHypothesis",
    "LayoutGroupKind",
    "LayoutPageKind",
    "PageLayoutProcessor",
    "PageLayoutResult",
]
