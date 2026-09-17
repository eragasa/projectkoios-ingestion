from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from itertools import repeat

import pytest
from projectkoios.ingestion import (
    BoundedProcessingCoordinator as PublicBoundedProcessingCoordinator,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    SourceDocument,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.processing import (
    BoundedProcessingCoordinator,
    ProcessingConfiguration,
    ProcessingDerivedArtifact,
    ProcessingFailure,
    ProcessingFailureKind,
    ProcessingInvocationResult,
    ProcessingLimitError,
    ProcessingPhysicalPageRange,
    ProcessingPrintedPageRange,
    ProcessingProcessorError,
    ProcessingProcessorIdentity,
    ProcessingRequest,
    ProcessingResourceIdentity,
    ProcessingResourceIdentityKind,
    ProcessingSelection,
    ProcessingSelectionResult,
    ProcessingStatus,
    ProcessingWarning,
    ProcessingWorkItem,
    build_derived_processing_cache_key,
)
from projectkoios.ingestion.protocols import (
    DerivedProcessingCache,
    ProcessingProcessor,
)
from projectkoios.ingestion.structure import (
    StructureAnalysis,
    StructureEvidenceStatus,
    StructureKind,
    StructureNode,
)


def _document() -> ExtractedDocument:
    source = SourceDocument.from_bytes(
        b"bounded-processing-source-v1",
        source_id="article:bounded-processing",
        media_type="application/pdf",
        locator="memory://bounded-processing.pdf",
    )
    pages: list[ExtractedPage] = []
    for page_index, label in enumerate(("i", "1", "2")):
        text = f"page-{page_index}-text"
        span = SourceSpan(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            page_index=page_index,
            printed_page_label=label,
            source_object_id=f"native:{page_index}",
            bounding_box=(10.0, 10.0, 90.0, 30.0),
            start_offset=0,
            end_offset=len(text),
        )
        block = ExtractedBlock.create(
            kind="text",
            source_spans=(span,),
            extraction_method="fixture",
            confidence=1.0,
            text=text,
        )
        pages.append(
            ExtractedPage(
                page_index=page_index,
                width=100.0,
                height=120.0,
                blocks=(block,),
                printed_page_label=label,
                coordinate_system="fixture",
            )
        )
    return ExtractedDocument.create(source=source, pages=tuple(pages))


def _structure(document: ExtractedDocument) -> StructureAnalysis:
    page = document.pages[1]
    block = page.blocks[0]
    node = StructureNode.create(
        kind=StructureKind.SECTION,
        source_spans=block.source_spans,
        evidence_type="fixture_heading",
        confidence=0.9,
        title="Selected section",
        source_block_ids=(block.block_id,),
        evidence_status=StructureEvidenceStatus.PROPOSED,
    )
    return StructureAnalysis.create(
        source=document.source,
        nodes=(node,),
        warnings=(),
        layout_result_ids=(),
        input_block_ids=(block.block_id,),
        processor_name="fixture-structure",
        processor_version="1",
        configuration_digest="fixture-structure-v1",
    )


def _identity(resource: str = "model-v1") -> ProcessingProcessorIdentity:
    return ProcessingProcessorIdentity(
        processor_name="recording-processor",
        processor_version="1",
        backend_name="fixture-backend",
        backend_version="1",
        configuration_digest="fixture-processor-config-v1",
        resources=(
            ProcessingResourceIdentity(
                resource_name="model",
                identity_kind=ProcessingResourceIdentityKind.EXPLICIT,
                resource_identity=resource,
            ),
        ),
    )


def _page_selection(
    document: ExtractedDocument, page_index: int
) -> ProcessingSelection:
    return ProcessingSelection.create(
        document=document,
        physical_page_ranges=(
            ProcessingPhysicalPageRange.create(
                start_page_index=page_index,
                end_page_index=page_index,
            ),
        ),
    )


def _region_selection(document: ExtractedDocument) -> ProcessingSelection:
    return ProcessingSelection.create(
        document=document,
        source_spans=(
            SourceSpan(
                source_id=document.source.source_id,
                source_blob_id=document.source.blob_id,
                page_index=0,
                printed_page_label="i",
                bounding_box=(20.0, 12.0, 40.0, 20.0),
            ),
        ),
    )


def _artifact(work_item: ProcessingWorkItem, content: bytes = b"derived"):
    return ProcessingDerivedArtifact.create(
        work_item=work_item,
        artifact_kind="fixture-derived-json",
        media_type="application/json",
        content=content,
        input_object_ids=work_item.input_object_ids[:1],
        source_spans=work_item.source_spans[:1],
        evidence=(("method", "fixture"),),
    )


class RecordingProcessor:
    name = "recording-processor"
    version = "1"

    def __init__(
        self,
        *,
        behavior: dict[str, str] | None = None,
        resource: str = "model-v1",
        content: bytes = b"derived",
    ) -> None:
        self.behavior = behavior or {}
        self.resource = resource
        self.content = content
        self.calls: list[ProcessingWorkItem] = []
        self.attempts: dict[str, int] = {}

    def identity_for(
        self, _work_item: ProcessingWorkItem
    ) -> ProcessingProcessorIdentity:
        return _identity(self.resource)

    def process(
        self, work_item: ProcessingWorkItem
    ) -> ProcessingInvocationResult:
        self.calls.append(work_item)
        attempt = self.attempts.get(work_item.selection_id, 0) + 1
        self.attempts[work_item.selection_id] = attempt
        behavior = self.behavior.get(work_item.selection_id, "completed")
        identity = self.identity_for(work_item)
        if behavior == "retry_then_complete" and attempt == 1:
            raise ProcessingProcessorError(
                kind=ProcessingFailureKind.PROCESSOR_UNAVAILABLE,
                message="The bounded backend is temporarily unavailable.",
                retryable=True,
            )
        if behavior == "retry_exhausted":
            raise ProcessingProcessorError(
                kind=ProcessingFailureKind.PROCESSOR_UNAVAILABLE,
                message="The bounded backend is temporarily unavailable.",
                retryable=True,
            )
        if behavior == "invalid_provenance":
            artifact = ProcessingDerivedArtifact.create(
                work_item=work_item,
                artifact_kind="fixture-invalid",
                media_type="application/octet-stream",
                content=b"invalid",
                input_object_ids=("unselected-object",),
            )
            return ProcessingInvocationResult.create(
                work_item=work_item,
                processor_identity=identity,
                status=ProcessingStatus.COMPLETED,
                artifacts=(artifact,),
            )
        if behavior == "failed":
            failure = ProcessingFailure.create(
                work_item=work_item,
                kind=ProcessingFailureKind.INPUT_REJECTED,
                message="The selected evidence is unsupported.",
                retryable=False,
            )
            return ProcessingInvocationResult.create(
                work_item=work_item,
                processor_identity=identity,
                status=ProcessingStatus.FAILED,
                failures=(failure,),
            )
        artifact = _artifact(work_item, self.content)
        if behavior == "partial":
            warning = ProcessingWarning.create(
                work_item=work_item,
                code="processing.fixture_partial",
                severity=WarningSeverity.WARNING,
                message="Only part of the selected evidence was processed.",
                object_ids=(work_item.input_object_ids[0],),
            )
            failure = ProcessingFailure.create(
                work_item=work_item,
                kind=ProcessingFailureKind.OUTPUT_INCOMPLETE,
                message="The processor returned incomplete output.",
                retryable=True,
            )
            return ProcessingInvocationResult.create(
                work_item=work_item,
                processor_identity=identity,
                status=ProcessingStatus.PARTIAL,
                artifacts=(artifact,),
                warnings=(warning,),
                failures=(failure,),
            )
        return ProcessingInvocationResult.create(
            work_item=work_item,
            processor_identity=identity,
            status=ProcessingStatus.COMPLETED,
            artifacts=(artifact,),
        )


class MemoryDerivedCache:
    def __init__(self) -> None:
        self.values: dict[str, ProcessingSelectionResult] = {}

    def get(self, cache_key: str) -> ProcessingSelectionResult | None:
        return self.values.get(cache_key)

    def put(self, cache_key: str, result: ProcessingSelectionResult) -> None:
        self.values[cache_key] = result


def test__processing_selection__resolves_page_region_node_and_union() -> None:
    document = _document()
    structure = _structure(document)
    node = structure.nodes[0]
    page = _page_selection(document, 2)
    region = _region_selection(document)
    node_selection = ProcessingSelection.create(
        document=document,
        structure_analysis=structure,
        structure_node_ids=(node.node_id,),
    )
    union = ProcessingSelection.create(
        document=document,
        source_spans=region.source_spans,
        physical_page_ranges=page.physical_page_ranges,
        structure_analysis=structure,
        structure_node_ids=(node.node_id,),
    )

    request = ProcessingRequest.create(
        selections=(page, region, node_selection, union)
    )

    assert request.work_items[0].full_page_indices == (2,)
    assert request.work_items[1].full_pages == ()
    assert request.work_items[1].source_spans == region.source_spans
    assert request.work_items[1].input_object_ids == ()
    assert request.work_items[2].full_pages == ()
    assert request.work_items[2].structure_nodes == (node,)
    assert request.work_items[3].full_page_indices == (2,)
    assert request.work_items[3].structure_nodes == (node,)
    assert region.source_spans[0] in request.work_items[3].source_spans


def test__processing_selection__supports_exact_printed_page_ranges() -> None:
    document = _document()
    selection = ProcessingSelection.create(
        document=document,
        printed_page_ranges=(
            ProcessingPrintedPageRange.create(
                start_printed_page_label="1",
                end_printed_page_label="2",
            ),
        ),
    )

    request = ProcessingRequest.create(selections=(selection,))

    assert request.work_items[0].full_page_indices == (1, 2)


def test__processing_coordinator__never_passes_unselected_pages() -> None:
    document = _document()
    selection = _page_selection(document, 1)
    processor = RecordingProcessor()
    result = BoundedProcessingCoordinator(processor).process(
        ProcessingRequest.create(selections=(selection,))
    )

    assert result.status is ProcessingStatus.COMPLETED
    assert len(processor.calls) == 1
    assert processor.calls[0].full_page_indices == (1,)
    assert all(span.page_index == 1 for span in processor.calls[0].source_spans)
    assert result.selection_results[0].artifacts[0].content == b"derived"


def test__processing_coordinator__preserves_partial_and_failed_selections() -> (
    None
):
    document = _document()
    completed = _page_selection(document, 0)
    partial = _page_selection(document, 1)
    failed = _page_selection(document, 2)
    processor = RecordingProcessor(
        behavior={
            partial.selection_id: "partial",
            failed.selection_id: "failed",
        }
    )

    result = BoundedProcessingCoordinator(processor).process(
        ProcessingRequest.create(selections=(completed, partial, failed))
    )

    assert result.status is ProcessingStatus.PARTIAL
    assert tuple(item.status for item in result.selection_results) == (
        ProcessingStatus.COMPLETED,
        ProcessingStatus.PARTIAL,
        ProcessingStatus.FAILED,
    )
    assert result.selection_results[1].artifacts
    assert result.selection_results[1].final_invocation.failures
    assert result.selection_results[2].artifacts == ()
    assert len(result.selection_results[2].attempts) == 1
    assert result.selection_results[2].final_invocation.failures[0].kind is (
        ProcessingFailureKind.INPUT_REJECTED
    )


def test__processing_coordinator__retries_only_retryable_failed_output() -> (
    None
):
    document = _document()
    retry_then_complete = _page_selection(document, 0)
    partial = _page_selection(document, 1)
    exhausted = _page_selection(document, 2)
    processor = RecordingProcessor(
        behavior={
            retry_then_complete.selection_id: "retry_then_complete",
            partial.selection_id: "partial",
            exhausted.selection_id: "retry_exhausted",
        }
    )

    result = BoundedProcessingCoordinator(processor).process(
        ProcessingRequest.create(
            selections=(retry_then_complete, partial, exhausted),
            configuration=ProcessingConfiguration(max_attempts_per_selection=2),
        )
    )

    first, second, third = result.selection_results
    assert tuple(attempt.invocation.status for attempt in first.attempts) == (
        ProcessingStatus.FAILED,
        ProcessingStatus.COMPLETED,
    )
    assert len(second.attempts) == 1
    assert second.status is ProcessingStatus.PARTIAL
    assert len(third.attempts) == 2
    assert third.retry_exhausted is True
    assert all(
        failure.retryable
        for attempt in third.attempts
        for failure in attempt.invocation.failures
    )


def test__processing_coordinator__reuses_only_nonfailed_cached_results() -> (
    None
):
    document = _document()
    selection = _page_selection(document, 1)
    processor = RecordingProcessor()
    cache = MemoryDerivedCache()
    coordinator = BoundedProcessingCoordinator(processor, cache=cache)
    request = ProcessingRequest.create(selections=(selection,))

    first = coordinator.process(request)
    second = coordinator.process(request)

    assert first == second
    assert len(processor.calls) == 1
    assert tuple(cache.values) == first.cache_keys


def test__processing_coordinator__does_not_cache_failed_results() -> None:
    document = _document()
    selection = _page_selection(document, 1)
    processor = RecordingProcessor(behavior={selection.selection_id: "failed"})
    cache = MemoryDerivedCache()
    coordinator = BoundedProcessingCoordinator(processor, cache=cache)
    request = ProcessingRequest.create(selections=(selection,))

    coordinator.process(request)
    coordinator.process(request)

    assert len(processor.calls) == 2
    assert cache.values == {}


def test__processing_cache_identity_covers_selection_config_and_resources() -> (
    None
):
    document = _document()
    first_request = ProcessingRequest.create(
        selections=(_page_selection(document, 0),)
    )
    work_item = first_request.work_items[0]
    baseline = build_derived_processing_cache_key(
        work_item,
        _identity(),
        first_request.configuration,
    )
    changed_selection_request = ProcessingRequest.create(
        selections=(_page_selection(document, 1),)
    )
    changed_selection = build_derived_processing_cache_key(
        changed_selection_request.work_items[0],
        _identity(),
        changed_selection_request.configuration,
    )
    changed_configuration = build_derived_processing_cache_key(
        work_item,
        _identity(),
        ProcessingConfiguration(max_attempts_per_selection=3),
    )
    changed_resource = build_derived_processing_cache_key(
        work_item,
        _identity("model-v2"),
        first_request.configuration,
    )
    changed_backend = build_derived_processing_cache_key(
        work_item,
        replace(_identity(), backend_version="2"),
        first_request.configuration,
    )

    assert (
        len(
            {
                baseline,
                changed_selection,
                changed_configuration,
                changed_resource,
                changed_backend,
            }
        )
        == 5
    )


def test__processing_coordinator__turns_output_limit_into_typed_failure() -> (
    None
):
    document = _document()
    selection = _page_selection(document, 0)
    processor = RecordingProcessor(content=b"too-large")
    request = ProcessingRequest.create(
        selections=(selection,),
        configuration=ProcessingConfiguration(max_artifact_bytes=1),
    )

    result = BoundedProcessingCoordinator(processor).process(request)

    assert result.status is ProcessingStatus.FAILED
    failure = result.selection_results[0].final_invocation.failures[0]
    assert failure.kind is ProcessingFailureKind.RESOURCE_LIMIT
    assert failure.retryable is False


def test__processing_coordinator__bounds_aggregate_artifact_bytes() -> None:
    document = _document()
    first = _page_selection(document, 0)
    second = _page_selection(document, 1)
    processor = RecordingProcessor(content=b"xx")
    cache = MemoryDerivedCache()
    request = ProcessingRequest.create(
        selections=(first, second),
        configuration=ProcessingConfiguration(
            max_artifact_bytes=2,
            max_total_artifact_bytes=3,
        ),
    )

    result = BoundedProcessingCoordinator(processor, cache=cache).process(
        request
    )

    assert result.status is ProcessingStatus.PARTIAL
    assert result.selection_results[0].status is ProcessingStatus.COMPLETED
    assert result.selection_results[1].status is ProcessingStatus.FAILED
    assert result.selection_results[1].final_invocation.failures[0].kind is (
        ProcessingFailureKind.RESOURCE_LIMIT
    )
    assert tuple(cache.values) == (result.selection_results[0].cache_key,)


def test__processing_coordinator__rejects_unselected_output_provenance() -> (
    None
):
    document = _document()
    selection = _page_selection(document, 0)
    processor = RecordingProcessor(
        behavior={selection.selection_id: "invalid_provenance"}
    )

    result = BoundedProcessingCoordinator(processor).process(
        ProcessingRequest.create(selections=(selection,))
    )

    assert result.status is ProcessingStatus.FAILED
    failure = result.selection_results[0].final_invocation.failures[0]
    assert failure.kind is ProcessingFailureKind.OUTPUT_INVALID
    assert failure.retryable is False


def test__processing_selection__rejects_stale_inputs_and_bounds_iterables() -> (
    None
):
    document = _document()
    selection = _page_selection(document, 0)
    wrong_source = SourceDocument.from_bytes(
        b"other",
        source_id=document.source.source_id,
        media_type="application/pdf",
        locator="memory://other.pdf",
    )
    stale_span = replace(
        document.pages[0].blocks[0].source_spans[0],
        source_blob_id=wrong_source.blob_id,
    )

    with pytest.raises(ValueError, match="document identity is stale"):
        ProcessingSelection.create(
            document=replace(document, document_id="stale-document"),
            physical_page_ranges=selection.physical_page_ranges,
        )
    with pytest.raises(ValueError, match="exact source"):
        ProcessingSelection.create(
            document=document,
            source_spans=(stale_span,),
        )
    with pytest.raises(ValueError, match="source object is stale"):
        ProcessingSelection.create(
            document=document,
            source_spans=(
                replace(
                    document.pages[0].blocks[0].source_spans[0],
                    source_object_id="missing-object",
                    start_offset=None,
                    end_offset=None,
                ),
            ),
        )
    with pytest.raises(ProcessingLimitError, match="page range is too large"):
        ProcessingSelection.create(
            document=document,
            physical_page_ranges=(
                ProcessingPhysicalPageRange.create(
                    start_page_index=0,
                    end_page_index=10_000_000,
                ),
            ),
        )
    with pytest.raises(ProcessingLimitError, match="selections"):
        ProcessingRequest.from_iterable(
            selections=repeat(selection),
            configuration=ProcessingConfiguration(max_selections=1),
        )


def test__processing_contracts__are_immutable_and_reject_stale_ids() -> None:
    document = _document()
    selection = _page_selection(document, 0)
    request = ProcessingRequest.create(selections=(selection,))
    result = BoundedProcessingCoordinator(RecordingProcessor()).process(request)

    with pytest.raises(FrozenInstanceError):
        selection.selection_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="selection ID is inconsistent"):
        replace(selection, selection_id="stale-selection")
    with pytest.raises(ValueError, match="request ID is inconsistent"):
        replace(request, request_id="stale-request")
    with pytest.raises(ValueError, match="result ID is inconsistent"):
        replace(result, result_id="processing-result:sha256:" + "0" * 64)


def test__processing_protocols_are_engine_neutral() -> None:
    assert PublicBoundedProcessingCoordinator is BoundedProcessingCoordinator
    processor: ProcessingProcessor = RecordingProcessor()
    cache: DerivedProcessingCache = MemoryDerivedCache()
    document = _document()
    request = ProcessingRequest.create(
        selections=(_region_selection(document),)
    )

    result = BoundedProcessingCoordinator(processor, cache=cache).process(
        request
    )

    assert result.status is ProcessingStatus.COMPLETED
    assert result.selection_results[0].processor_identity == (
        processor.identity_for(request.work_items[0])
    )
