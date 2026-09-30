from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion import (
    DeterministicLayoutProcessor as RootDeterministicLayoutProcessor,
)
from projectkoios.ingestion import (
    LayoutConfiguration as RootLayoutConfiguration,
)
from projectkoios.ingestion.layout import (
    DeterministicLayoutProcessor,
    LayoutAnalysisActionizer,
    LayoutAnalysisRequest,
    LayoutAnalysisResult,
    LayoutConfiguration,
)
from projectkoios.ingestion.layout import __all__ as layout_api
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.pdf import PYMUPDF_COORDINATE_SYSTEM


def _document() -> ExtractedDocument:
    source = SourceDocument.from_bytes(
        b"%PDF-1.7\nlayout actionizer fixture\n%%EOF\n",
        source_id="fixture:layout-actionizer",
        media_type="application/pdf",
        locator="fixture://layout-actionizer.pdf",
    )
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                source_object_id="fixture:layout:block:0",
                bounding_box=(10.0, 10.0, 90.0, 20.0),
            ),
        ),
        extraction_method="fixture-extractor",
        confidence=1.0,
        text="Exact page text.",
    )
    return ExtractedDocument.create(
        source=source,
        pages=(
            ExtractedPage(
                page_index=0,
                width=100.0,
                height=100.0,
                blocks=(block,),
                coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            ),
        ),
    )


def test__layout_actionizer_binds_request_configuration_and_results() -> None:
    configuration = LayoutConfiguration()
    request = LayoutAnalysisRequest.create(
        document=_document(),
        configuration=configuration,
    )

    actionizer = LayoutAnalysisActionizer()
    result = actionizer.action(request=request)
    legacy_results = DeterministicLayoutProcessor(
        configuration=configuration
    ).analyze(document=request.document)

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(result, DataObjectActionResult)
    assert isinstance(actionizer, DataObjectActionizer)
    assert result.request_id == request.request_id
    assert result.page_results == legacy_results
    assert result.configuration_digest == configuration.configuration_digest
    assert result.actionizer_name == "deterministic-layout-analysis-actionizer"
    assert result.actionizer_version == "1"
    assert actionizer.execute(request=request) == result

    with pytest.raises(ValueError, match="request ID"):
        replace(request, request_id="layout-analysis-request:invalid")
    with pytest.raises(ValueError, match="result ID"):
        replace(result, result_id="layout-analysis-action-result:invalid")
    with pytest.raises(TypeError, match="LayoutAnalysisRequest"):
        LayoutAnalysisActionizer().execute(
            request=request.document  # type: ignore[arg-type]
        )


def test__layout_request_identity_changes_with_configuration() -> None:
    document = _document()
    first = LayoutAnalysisRequest.create(
        document=document,
        configuration=LayoutConfiguration(),
    )
    second = LayoutAnalysisRequest.create(
        document=document,
        configuration=LayoutConfiguration(minimum_column_gap_ratio=0.05),
    )

    assert first.request_id != second.request_id


def test__layout_facade_preserves_old_imports_without_implementation() -> None:
    assert RootDeterministicLayoutProcessor is DeterministicLayoutProcessor
    assert RootLayoutConfiguration is LayoutConfiguration
    assert DeterministicLayoutProcessor.__module__ == (
        "projectkoios.ingestion.layout"
    )
    assert LayoutConfiguration.__module__ == "projectkoios.ingestion.layout"
    assert LayoutAnalysisActionizer.__module__ == (
        "projectkoios.ingestion.layout.actionizer"
    )
    assert LayoutAnalysisRequest.__module__ == (
        "projectkoios.ingestion.layout.actionizer"
    )
    assert LayoutAnalysisResult.__module__ == (
        "projectkoios.ingestion.layout.actionizer"
    )
    assert "LayoutAnalysisActionizer" in layout_api
    assert "LayoutAnalysisRequest" in layout_api
    assert "LayoutAnalysisResult" in layout_api
