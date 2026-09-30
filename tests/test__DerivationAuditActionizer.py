from __future__ import annotations

from dataclasses import replace

import pytest
from projectkoios.base import (
    DataObjectActionizer,
    DataObjectActionRequest,
    DataObjectActionResult,
)
from projectkoios.ingestion import (
    DerivationAuditInput as RootDerivationAuditInput,
)
from projectkoios.ingestion import (
    DerivationAuditReport as RootDerivationAuditReport,
)
from projectkoios.ingestion import (
    DerivationAuditValidator as RootDerivationAuditValidator,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    SourceDocument,
    SourceSpan,
)
from projectkoios.ingestion.provenance import (
    DerivationAuditActionizer,
    DerivationAuditInput,
    DerivationAuditReport,
    DerivationAuditRequest,
    DerivationAuditResult,
    DerivationAuditValidator,
)
from projectkoios.ingestion.provenance import __all__ as provenance_api


def _audit_input(content: bytes) -> DerivationAuditInput:
    source = SourceDocument.from_bytes(
        content,
        source_id="fixture:actionizer-taxonomy",
        media_type="application/pdf",
        locator="fixture://actionizer-taxonomy.pdf",
    )
    block = ExtractedBlock.create(
        kind="text",
        source_spans=(
            SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=0,
                source_object_id="fixture:block:0",
                bounding_box=(10.0, 10.0, 90.0, 20.0),
            ),
        ),
        extraction_method="fixture-extractor",
        confidence=1.0,
        text="Bounded public evidence.",
    )
    page = ExtractedPage(
        page_index=0,
        width=100.0,
        height=100.0,
        blocks=(block,),
        coordinate_system="fixture-points-top-left",
    )
    document = ExtractedDocument.create(source=source, pages=(page,))
    manifest = IngestionManifest.create(
        source=source,
        extractor_name="fixture-extractor",
        extractor_version="1",
        configuration_digest="fixture-configuration",
        object_ids=(document.document_id, block.block_id),
        warning_ids=(),
        status=IngestionStatus.COMPLETED,
        started_at="2026-09-30T00:00:00Z",
        completed_at="2026-09-30T00:00:01Z",
    )
    return DerivationAuditInput(
        source_content=content,
        extraction_result=ExtractionResult(
            document=document,
            manifest=manifest,
        ),
    )


def test__actionizer_binds_exact_request_result_and_actionizer_identity() -> (
    None
):
    audit_input = _audit_input(
        b"%PDF-1.7\nactionizer taxonomy fixture\n%%EOF\n"
    )
    request = DerivationAuditRequest.create(audit_input=audit_input)
    repeated_request = DerivationAuditRequest.create(audit_input=audit_input)

    actionizer = DerivationAuditActionizer()
    result = actionizer.action(request=request)
    repeated_result = actionizer.execute(request=repeated_request)

    assert isinstance(request, DataObjectActionRequest)
    assert isinstance(result, DataObjectActionResult)
    assert isinstance(actionizer, DataObjectActionizer)
    assert request == repeated_request
    assert result == repeated_result
    assert result.request_id == request.request_id
    assert result.actionizer_name == (
        "deterministic-derivation-audit-actionizer"
    )
    assert result.actionizer_version == "1"
    assert result.report.processor_version == "2"
    assert result.valid
    assert result.status is result.report.status
    result.require_valid()

    with pytest.raises(ValueError, match="request ID"):
        replace(request, request_id="derivation-audit-request:invalid")
    with pytest.raises(ValueError, match="result ID"):
        replace(result, result_id="derivation-audit-action-result:invalid")
    with pytest.raises(TypeError, match="DerivationAuditRequest"):
        DerivationAuditActionizer().execute(
            request=audit_input  # type: ignore[arg-type]
        )


def test__request_identity_changes_with_exact_source_bytes() -> None:
    first = DerivationAuditRequest.create(
        audit_input=_audit_input(b"%PDF-1.7\nfirst\n%%EOF\n")
    )
    second = DerivationAuditRequest.create(
        audit_input=_audit_input(b"%PDF-1.7\nsecond\n%%EOF\n")
    )

    assert first.request_id != second.request_id


def test__legacy_api_and_import_paths_remain_exact_compatibility_aliases() -> (
    None
):
    assert issubclass(DerivationAuditValidator, DerivationAuditActionizer)
    assert RootDerivationAuditValidator is DerivationAuditValidator
    assert RootDerivationAuditInput is DerivationAuditInput
    assert RootDerivationAuditReport is DerivationAuditReport
    assert DerivationAuditActionizer.__module__ == (
        "projectkoios.ingestion.provenance.audit"
    )
    assert DerivationAuditValidator.__module__ == (
        "projectkoios.ingestion.provenance"
    )
    assert DerivationAuditRequest.__module__ == (
        "projectkoios.ingestion.provenance.audit"
    )
    assert DerivationAuditResult.__module__ == (
        "projectkoios.ingestion.provenance.audit"
    )
    assert "DerivationAuditActionizer" in provenance_api
    assert "DerivationAuditRequest" in provenance_api
    assert "DerivationAuditResult" in provenance_api
