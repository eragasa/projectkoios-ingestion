"""Pure derivation of sanitized page-projection evidence enrichments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.page.projection.block import (
    PageProjectionTextBlock,
    PageProjectionTextBlockStyle,
)
from projectkoios.ingestion.page.projection.enrichment.basis import (
    PageProjectionEvidenceRetainedTextBasis,
    PageProjectionEvidenceStyle,
    PageProjectionEvidenceUnavailableReason,
    PageProjectionEvidenceWarningDetailStatus,
)
from projectkoios.ingestion.page.projection.enrichment.binding import (
    PageProjectionEvidenceCrossBinding,
)
from projectkoios.ingestion.page.projection.enrichment.identity import (
    PageProjectionEvidenceAffectedIdentity,
    PageProjectionEvidenceAffectedIdentityInventory,
    PageProjectionEvidenceIdentityInventory,
)
from projectkoios.ingestion.page.projection.enrichment.inventory import (
    PageProjectionEvidenceEnrichmentInventory,
)
from projectkoios.ingestion.page.projection.enrichment.limitation import (
    PageProjectionEvidenceLimitation,
    PageProjectionEvidenceLimitationCode,
    PageProjectionEvidenceLimitationInventory,
)
from projectkoios.ingestion.page.projection.enrichment.producer import (
    PageProjectionEvidenceProducerBinding,
    PageProjectionEvidenceProducerBindingInventory,
)
from projectkoios.ingestion.page.projection.enrichment.record import (
    PageProjectionEvidenceEnrichment,
    PageProjectionEvidenceEntry,
    PageProjectionEvidenceUnavailable,
)
from projectkoios.ingestion.page.projection.enrichment.warning import (
    PageProjectionEvidenceWarning,
    PageProjectionEvidenceWarningInventory,
)
from projectkoios.ingestion.page.projection.error import PageProjectionError
from projectkoios.ingestion.page.projection.page import PageProjectionPage
from projectkoios.ingestion.transcript.reading.evidence.association.role import (  # noqa: E501
    ReadingAssociationRole,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.definition import (  # noqa: E501
    ReadingEvidenceLimitation,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.inventory import (  # noqa: E501
    ReadingEvidenceLimitationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.page.projection.result import (
        PageProjectionResult,
    )


EvidenceApplicabilityKey = tuple[str, str]


def project_page_projection_evidence_limitations(
    *,
    limitations: ReadingEvidenceLimitationInventory,
    applicable_ids: set[EvidenceApplicabilityKey],
) -> PageProjectionEvidenceLimitationInventory:
    """Project exact limitations whose affected identities touch one entry."""
    projected: list[PageProjectionEvidenceLimitation] = []
    for limitation in limitations:
        if type(limitation) is not ReadingEvidenceLimitation:
            raise TypeError("reading limitation has an unsupported type")
        affected = tuple(limitation.affected_ids)
        keys = {(value.kind.value, value.value) for value in affected}
        if not keys.intersection(applicable_ids):
            continue
        projected.append(
            PageProjectionEvidenceLimitation(
                limitation_id=limitation.limitation_id.value,
                code=PageProjectionEvidenceLimitationCode(
                    limitation.code.value
                ),
                affected_ids=(
                    PageProjectionEvidenceAffectedIdentityInventory(
                        *(
                            PageProjectionEvidenceAffectedIdentity(
                                kind=value.kind.value,
                                value=value.value,
                            )
                            for value in affected
                        )
                    )
                ),
            )
        )
    return PageProjectionEvidenceLimitationInventory(
        *sorted(projected, key=lambda value: value.limitation_id)
    )


def derive_page_projection_evidence_cross_binding(
    *,
    result: PageProjectionResult,
    page: PageProjectionPage,
    block: PageProjectionTextBlock,
) -> PageProjectionEvidenceCrossBinding:
    """Return one exact downstream join binding without Search knowledge."""
    return PageProjectionEvidenceCrossBinding(
        page_projection_result_id=result.result_id,
        source_result_id=result.source_result_id,
        reading_projection_result_id=result.projection_result_id.value,
        artifact_verification_result_id=(
            result.artifact_verification_result_id
        ),
        source_id=result.source_id.value,
        document_id=result.document_id.value,
        source_page_id=page.source_page_id.value,
        page_location_id=page.page_location.location_id.value,
        page_projection_page_id=page.page_id,
        page_projection_block_id=block.block_id,
        source_evidence_id=block.source_id.value,
        style=PageProjectionEvidenceStyle(block.style.value),
    )


def derive_page_projection_text_warning_inventory(
    *, block: ReadingTextEvidenceBlock
) -> PageProjectionEvidenceWarningInventory:
    """Retain warning IDs and only their exact graph-visible affected IDs."""
    affected_by_warning: dict[str, list[str]] = {}
    for source in block.sources:
        source_warning_ids = tuple(value.value for value in source.warning_ids)
        for warning_id in source_warning_ids:
            affected = affected_by_warning.setdefault(warning_id, [])
            span_ids = [
                span.span_id.value
                for span in source.source_spans
                if span.geometry_warning_id is not None
                and span.geometry_warning_id.value == warning_id
            ]
            if span_ids:
                affected.extend(span_ids)
            else:
                affected.append(source.record_id.value)
    records = []
    for warning_id in sorted(affected_by_warning):
        affected = list(dict.fromkeys(affected_by_warning[warning_id]))
        records.append(
            PageProjectionEvidenceWarning(
                warning_id=warning_id,
                affected_ids=PageProjectionEvidenceIdentityInventory(*affected),
                detail_status=(
                    PageProjectionEvidenceWarningDetailStatus.UNAVAILABLE
                ),
                detail=None,
            )
        )
    return PageProjectionEvidenceWarningInventory(*records)


def derive_page_projection_text_applicability(
    *,
    page: ReadingEvidencePage,
    block: ReadingTextEvidenceBlock,
) -> set[EvidenceApplicabilityKey]:
    """Return exact typed identities visibly bound to one text block."""
    values: set[EvidenceApplicabilityKey] = {
        (ReadingEvidenceIdentityKind.BLOCK.value, block.block_id.value),
        (
            ReadingEvidenceIdentityKind.STRUCTURED_ITEM.value,
            block.structured_item.record_id.value,
        ),
        (
            ReadingEvidenceIdentityKind.EVIDENCE_PAGE.value,
            page.page_id.value,
        ),
        (
            ReadingEvidenceIdentityKind.PAGE_LOCATION.value,
            page.page_location.location_id.value,
        ),
    }
    for source in block.sources:
        values.add(
            (
                ReadingEvidenceIdentityKind.CLEAN_TEXT.value,
                source.record_id.value,
            )
        )
        values.add(
            (
                ReadingEvidenceIdentityKind.SOURCE_BLOCK.value,
                source.source_block_id.value,
            )
        )
        for span in source.source_spans:
            values.add(
                (
                    ReadingEvidenceIdentityKind.SOURCE_SPAN.value,
                    span.span_id.value,
                )
            )
        for warning in source.warning_ids:
            values.add(
                (ReadingEvidenceIdentityKind.WARNING.value, warning.value)
            )
    return values


def derive_page_projection_text_enrichment(
    *,
    result: PageProjectionResult,
    projected_page: PageProjectionPage,
    projected_block: PageProjectionTextBlock,
    source_page: ReadingEvidencePage,
    source_block: ReadingTextEvidenceBlock,
) -> PageProjectionEvidenceEnrichment:
    """Derive one exact raw-text enrichment for a paragraph or heading."""
    if projected_block.source_id != source_block.block_id:
        raise PageProjectionError("projected text block source is inconsistent")
    sources = tuple(source_block.sources)
    retained_text = "\n".join(value.raw_text for value in sources)
    span_ids = tuple(
        span.span_id.value for source in sources for span in source.source_spans
    )
    producers = PageProjectionEvidenceProducerBindingInventory(
        *(
            PageProjectionEvidenceProducerBinding(
                source_record_id=source.record_id.value,
                source_block_id=source.source_block_id.value,
                producer_id=source.producer_id.value,
                producer_version=source.producer_version,
            )
            for source in sources
        )
    )
    applicability = derive_page_projection_text_applicability(
        page=source_page,
        block=source_block,
    )
    return PageProjectionEvidenceEnrichment(
        binding=derive_page_projection_evidence_cross_binding(
            result=result,
            page=projected_page,
            block=projected_block,
        ),
        retained_text=retained_text,
        retained_text_basis=(
            PageProjectionEvidenceRetainedTextBasis.TEXT_BLOCK_RAW_SOURCE_SEQUENCE
        ),
        producers=producers,
        source_span_ids=PageProjectionEvidenceIdentityInventory(*span_ids),
        warnings=derive_page_projection_text_warning_inventory(
            block=source_block
        ),
        limitations=project_page_projection_evidence_limitations(
            limitations=result.reading_evidence_limitations,
            applicable_ids=applicability,
        ),
    )


def derive_page_projection_caption_applicability(
    *,
    page: ReadingEvidencePage,
    block: ReadingFigureEvidenceBlock,
) -> set[EvidenceApplicabilityKey]:
    """Return exact identities bound to one unavailable projected caption."""
    caption = block.caption
    if caption is None:
        raise PageProjectionError("projected caption source is absent")
    values: set[EvidenceApplicabilityKey] = {
        (ReadingEvidenceIdentityKind.BLOCK.value, block.block_id.value),
        (
            ReadingEvidenceIdentityKind.STRUCTURED_ITEM.value,
            block.structured_item.record_id.value,
        ),
        (
            ReadingEvidenceIdentityKind.FIGURE.value,
            block.producer_evidence.record_id.value,
        ),
        (ReadingEvidenceIdentityKind.CAPTION.value, caption.caption_id.value),
        (
            ReadingEvidenceIdentityKind.SOURCE_OBJECT.value,
            block.producer_evidence.lineage.source_object_id.value,
        ),
        (
            ReadingEvidenceIdentityKind.EVIDENCE_PAGE.value,
            page.page_id.value,
        ),
        (
            ReadingEvidenceIdentityKind.PAGE_LOCATION.value,
            page.page_location.location_id.value,
        ),
    }
    caption_ids = {value.value for value in caption.association_ids}
    for association in block.producer_evidence.assessment.associations:
        if association.association_id.value not in caption_ids:
            continue
        if association.role is not ReadingAssociationRole.CAPTION:
            raise PageProjectionError(
                "caption identity binds a non-caption association"
            )
        values.add(
            (
                ReadingEvidenceIdentityKind.ASSOCIATION.value,
                association.association_id.value,
            )
        )
        for source_block_id in association.source_block_ids:
            values.add(
                (
                    ReadingEvidenceIdentityKind.SOURCE_BLOCK.value,
                    source_block_id.value,
                )
            )
        for span in association.source_spans:
            values.add(
                (
                    ReadingEvidenceIdentityKind.SOURCE_SPAN.value,
                    span.span_id.value,
                )
            )
            if span.geometry_warning_id is not None:
                values.add(
                    (
                        ReadingEvidenceIdentityKind.WARNING.value,
                        span.geometry_warning_id.value,
                    )
                )
    for warning in block.producer_evidence.lineage.warning_ids:
        values.add((ReadingEvidenceIdentityKind.WARNING.value, warning.value))
    return values


def derive_page_projection_caption_unavailable(
    *,
    result: PageProjectionResult,
    projected_page: PageProjectionPage,
    projected_block: PageProjectionTextBlock,
    source_page: ReadingEvidencePage,
    source_block: ReadingFigureEvidenceBlock,
) -> PageProjectionEvidenceUnavailable:
    """Emit a keyed fail-closed disposition for normalized captions."""
    caption = source_block.caption
    if caption is None or projected_block.source_id != caption.caption_id:
        raise PageProjectionError("projected caption source is inconsistent")
    applicability = derive_page_projection_caption_applicability(
        page=source_page,
        block=source_block,
    )
    return PageProjectionEvidenceUnavailable(
        binding=derive_page_projection_evidence_cross_binding(
            result=result,
            page=projected_page,
            block=projected_block,
        ),
        reason=(
            PageProjectionEvidenceUnavailableReason.FIGURE_CAPTION_HAS_NO_EXACT_RAW_CLEAN_PAIR
        ),
        producer_record_ids=PageProjectionEvidenceIdentityInventory(
            source_block.producer_evidence.record_id.value
        ),
        limitations=project_page_projection_evidence_limitations(
            limitations=result.reading_evidence_limitations,
            applicable_ids=applicability,
        ),
    )


def derive_page_projection_evidence_enrichments(
    *, result: PageProjectionResult
) -> PageProjectionEvidenceEnrichmentInventory:
    """Return one exact available or unavailable entry per projected block."""
    from projectkoios.ingestion.page.projection.result import (
        PageProjectionResult,
    )

    if type(result) is not PageProjectionResult:
        raise TypeError("result must be PageProjectionResult")
    source_pages = {
        page.page_id.value: page
        for page in result.request.source_result.document.pages
    }
    entries: list[PageProjectionEvidenceEntry] = []
    for projected_page in result.pages:
        source_page = source_pages.get(projected_page.source_page_id.value)
        if source_page is None or source_page.page_location != (
            projected_page.page_location
        ):
            raise PageProjectionError(
                "projected page has no exact canonical source page"
            )
        source_by_id: dict[
            str, ReadingTextEvidenceBlock | ReadingFigureEvidenceBlock
        ] = {}
        for source_block in source_page.blocks:
            if type(source_block) is ReadingTextEvidenceBlock:
                source_by_id[source_block.block_id.value] = source_block
            elif (
                type(source_block) is ReadingFigureEvidenceBlock
                and source_block.caption is not None
            ):
                source_by_id[source_block.caption.caption_id.value] = (
                    source_block
                )
        for projected_block in projected_page.blocks:
            matched_source = source_by_id.get(projected_block.source_id.value)
            if type(matched_source) is ReadingTextEvidenceBlock:
                if projected_block.style not in (
                    PageProjectionTextBlockStyle.PARAGRAPH,
                    PageProjectionTextBlockStyle.HEADING,
                ):
                    raise PageProjectionError(
                        "projected text source has a non-text style"
                    )
                entries.append(
                    derive_page_projection_text_enrichment(
                        result=result,
                        projected_page=projected_page,
                        projected_block=projected_block,
                        source_page=source_page,
                        source_block=matched_source,
                    )
                )
            elif type(matched_source) is ReadingFigureEvidenceBlock:
                if (
                    projected_block.style
                    is not PageProjectionTextBlockStyle.FIGURE_CAPTION
                ):
                    raise PageProjectionError(
                        "projected caption source has a non-caption style"
                    )
                entries.append(
                    derive_page_projection_caption_unavailable(
                        result=result,
                        projected_page=projected_page,
                        projected_block=projected_block,
                        source_page=source_page,
                        source_block=matched_source,
                    )
                )
            else:
                raise PageProjectionError(
                    "projected block has no enrichable canonical source"
                )
    return PageProjectionEvidenceEnrichmentInventory(*entries)
