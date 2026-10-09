"""Immutable request for pure current-schema page projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.base import DataObjectActionRequest
from projectkoios.ingestion.artifact.managed.verification.evidence import (
    ManagedArtifactVerificationEvidence,
    ManagedArtifactVerificationEvidenceInventory,
)
from projectkoios.ingestion.artifact.managed.verification.request import (
    ManagedArtifactVerificationRequest,
)
from projectkoios.ingestion.artifact.managed.verification.result import (
    ManagedArtifactVerificationResult,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.identity import (
    PageProjectionInputIdentityDerivation,
)
from projectkoios.ingestion.page.projection.limits.definition import (
    PAGE_PROJECTION_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlock,
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.source import (  # noqa: E501
    ReadingTextBlockSourceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.document.definition import (  # noqa: E501
    ReadingEvidenceDocument,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.source import (  # noqa: E501
    ReadingSourceBlockIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.inventory.definition import (  # noqa: E501
    ReadingEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)


def _reconstruct_page_projection_caption(
    caption: ReadingCaptionEvidence,
) -> ReadingCaptionEvidence:
    associations = ReadingEvidenceIdentityInventory(
        caption.association_ids.kind,
        *caption.association_ids,
    )
    return ReadingCaptionEvidence(
        text=caption.text,
        association_ids=associations,
        basis=caption.basis,
    )


def _reconstruct_page_projection_block(
    *,
    block: ReadingEvidenceBlock,
    page_location: ReadingPageLocation,
) -> ReadingEvidenceBlock:
    item = block.structured_item
    fresh_item = ReadingStructuredItemProducerEvidence(
        page_location=page_location,
        order_index=item.order_index,
        kind=item.kind,
        source_block_ids=ReadingSourceBlockIdentityInventory(
            *item.source_block_ids
        ),
        source_object_id=item.source_object_id,
        producer_id=item.producer_id,
        producer_version=item.producer_version,
    )
    if type(block) is ReadingTextEvidenceBlock:
        return ReadingTextEvidenceBlock(
            structured_item=fresh_item,
            sources=ReadingTextBlockSourceInventory(*block.sources),
            basis=block.basis,
        )
    if type(block) is ReadingFigureEvidenceBlock:
        caption = (
            None
            if block.caption is None
            else _reconstruct_page_projection_caption(block.caption)
        )
        return ReadingFigureEvidenceBlock(
            structured_item=fresh_item,
            producer_evidence=block.producer_evidence,
            caption=caption,
        )
    if type(block) is ReadingTableEvidenceBlock:
        return ReadingTableEvidenceBlock(
            structured_item=fresh_item,
            producer_evidence=block.producer_evidence,
        )
    if type(block) is ReadingEquationEvidenceBlock:
        return ReadingEquationEvidenceBlock(
            structured_item=fresh_item,
            producer_evidence=block.producer_evidence,
        )
    raise PageProjectionError("canonical page has an unsupported block")


def _reconstruct_page_projection_pages(
    document: ReadingEvidenceDocument,
) -> ReadingEvidencePageInventory:
    source_pages = tuple(document.pages)
    source_blocks = tuple(
        block for page in source_pages for block in page.blocks
    )
    PAGE_PROJECTION_LIMITS.require_count(
        len(source_pages) + len(source_blocks),
        "page projection freshness work",
        maximum=PAGE_PROJECTION_LIMITS.maximum_total_work,
    )
    pages: list[ReadingEvidencePage] = []
    for page in source_pages:
        location = page.page_location
        fresh_location = ReadingPageLocation(
            physical_page_index=location.physical_page_index,
            printed_page_label=location.printed_page_label,
        )
        if fresh_location != location:
            raise PageProjectionError("canonical page location is stale")
        page_text = page.page_text
        fresh_streams = ReadingTextStreamEvidenceInventory(*page_text.streams)
        fresh_page_text = ReadingPageTextProducerEvidence(
            streams=fresh_streams,
            selection=page_text.selection,
            producer_id=page_text.producer_id,
            producer_version=page_text.producer_version,
            review_status=page_text.review_status,
        )
        fresh_blocks = ReadingEvidenceBlockInventory(
            *(
                _reconstruct_page_projection_block(
                    block=block,
                    page_location=fresh_location,
                )
                for block in page.blocks
            )
        )
        pages.append(
            ReadingEvidencePage(
                page_text=fresh_page_text,
                blocks=fresh_blocks,
            )
        )
    return ReadingEvidencePageInventory(*pages)


def validate_page_projection_source_result(
    *, source_result: ReadingEvidenceSourceResult
) -> None:
    """Require a fresh exact canonical source-result binding."""
    if type(source_result) is not ReadingEvidenceSourceResult:
        raise TypeError("source_result must be ReadingEvidenceSourceResult")
    try:
        fresh_pages = _reconstruct_page_projection_pages(source_result.document)
    except PageProjectionError:
        raise
    except (TypeError, ValueError) as error:
        raise PageProjectionError(
            "canonical page projection evidence is stale"
        ) from error
    if fresh_pages != source_result.document.pages:
        raise PageProjectionError(
            "canonical page projection evidence identities are stale"
        )
    observed_inventory = ReadingEvidenceInventory.observe(
        source_result.document
    )
    if observed_inventory != source_result.inventory:
        raise PageProjectionError(
            "source result inventory differs from the document"
        )
    fresh_request = ReadingEvidenceSourceRequest(
        provider_source_id=source_result.request.provider_source_id,
        document_id=source_result.request.document_id,
        projection_result_id=source_result.request.projection_result_id,
        inventory_id=source_result.request.inventory_id,
        maximum_page_count=source_result.request.maximum_page_count,
        maximum_block_count=source_result.request.maximum_block_count,
        maximum_artifact_count=source_result.request.maximum_artifact_count,
        maximum_provider_record_count=(
            source_result.request.maximum_provider_record_count
        ),
        authority_id=source_result.request.authority_id,
    )
    fresh_result = ReadingEvidenceSourceResult(
        request=fresh_request,
        document=source_result.document,
        inventory=observed_inventory,
        projection_result_id=source_result.projection_result_id,
        provider_implementation_id=(source_result.provider_implementation_id),
        provider_verification_id=source_result.provider_verification_id,
    )
    if fresh_request != source_result.request or fresh_result != source_result:
        raise PageProjectionError("source result identities are stale")


def validate_page_projection_artifact_verification(
    *,
    document: ReadingEvidenceDocument,
    verification: ManagedArtifactVerificationResult,
) -> None:
    """Require fresh exact successful coverage of document references."""
    if type(verification) is not ManagedArtifactVerificationResult:
        raise TypeError(
            "artifact_verification_result must be "
            "ManagedArtifactVerificationResult"
        )
    if verification.request.references != document.managed_artifacts:
        raise PageProjectionError(
            "artifact verification covers different references"
        )
    PAGE_PROJECTION_LIMITS.require_count(
        len(verification.evidence),
        "managed artifact verification count",
        maximum=PAGE_PROJECTION_LIMITS.maximum_verification_evidence,
    )
    PAGE_PROJECTION_LIMITS.require_count(
        verification.evidence.aggregate_observed_byte_length,
        "managed artifact observed bytes",
        maximum=PAGE_PROJECTION_LIMITS.maximum_observed_artifact_bytes,
    )
    fresh_evidence = tuple(
        ManagedArtifactVerificationEvidence(
            reference=value.reference,
            observed_sha256=value.observed_sha256,
            observed_byte_length=value.observed_byte_length,
            observed_media_type=value.observed_media_type,
            provider_implementation_id=value.provider_implementation_id,
            verifier_implementation_id=value.verifier_implementation_id,
        )
        for value in verification.evidence
    )
    fresh_request = ManagedArtifactVerificationRequest(
        references=verification.request.references,
        provider_implementation_id=(
            verification.request.provider_implementation_id
        ),
        authority_id=verification.request.authority_id,
        maximum_artifact_bytes=(verification.request.maximum_artifact_bytes),
        maximum_aggregate_bytes=(verification.request.maximum_aggregate_bytes),
        stream_chunk_bytes=verification.request.stream_chunk_bytes,
    )
    fresh_inventory = ManagedArtifactVerificationEvidenceInventory(
        fresh_request.references,
        *fresh_evidence,
    )
    fresh_result = ManagedArtifactVerificationResult(
        request=fresh_request,
        evidence=fresh_inventory,
        verifier_implementation_id=verification.verifier_implementation_id,
    )
    if fresh_request != verification.request or (
        fresh_inventory != verification.evidence or fresh_result != verification
    ):
        raise PageProjectionError("artifact verification identities are stale")


@dataclass(frozen=True, slots=True)
class PageProjectionRequest(DataObjectActionRequest):
    """Bind one canonical source result to exact verified artifacts."""

    CONTRACT_NAME: ClassVar[str] = "page-projection-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    source_result: ReadingEvidenceSourceResult
    artifact_verification_result: ManagedArtifactVerificationResult
    include_figure_captions: bool
    request_id: str = field(init=False)

    def __post_init__(self) -> None:
        validate_page_projection_source_result(source_result=self.source_result)
        if type(self.include_figure_captions) is not bool:
            raise TypeError("include_figure_captions must be an exact bool")
        validate_page_projection_artifact_verification(
            document=self.source_result.document,
            verification=self.artifact_verification_result,
        )
        work_count = (
            len(self.source_result.document.pages)
            + self.source_result.inventory.measures.block_count
            + len(self.artifact_verification_result.evidence)
        )
        PAGE_PROJECTION_LIMITS.require_count(
            work_count,
            "page projection work",
            maximum=PAGE_PROJECTION_LIMITS.maximum_total_work,
        )
        object.__setattr__(
            self,
            "request_id",
            PageProjectionInputIdentityDerivation.derive(
                source_result_id=self.source_result.result_id,
                artifact_verification_result_id=(
                    self.artifact_verification_result.result_id
                ),
                include_figure_captions=self.include_figure_captions,
                contract_version=self.CONTRACT_VERSION,
            ),
        )


def validate_page_projection_request_freshness(
    *, request: PageProjectionRequest
) -> None:
    """Reject post-construction changes to any request binding."""
    if type(request) is not PageProjectionRequest:
        raise TypeError("request must be PageProjectionRequest")
    try:
        fresh_request = PageProjectionRequest(
            source_result=request.source_result,
            artifact_verification_result=(request.artifact_verification_result),
            include_figure_captions=request.include_figure_captions,
        )
    except PageProjectionError:
        raise
    except (TypeError, ValueError) as error:
        raise PageProjectionError("page projection request is stale") from error
    if fresh_request != request:
        raise PageProjectionError("page projection request identity is stale")
