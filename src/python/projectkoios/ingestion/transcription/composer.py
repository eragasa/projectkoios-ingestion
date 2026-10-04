from __future__ import annotations

from projectkoios.base import (
    DataObjectActionizer,
)
from projectkoios.ingestion.models import (
    ExtractedBlock,
    IngestionWarning,
    WarningSeverity,
)
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.derivation.equation import (
    EquationTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.figure import (
    FigureTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.order import (
    TranscriptionOrderDerivation,
)
from projectkoios.ingestion.transcription.derivation.page import (
    PageTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.raw_block import (
    RawBlockTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.structure import (
    StructureTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.structure_disposition import (  # noqa: E501
    TranscriptionStructureDisposition,
)
from projectkoios.ingestion.transcription.derivation.table import (
    TableTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.warning import (
    TranscriptionWarningDerivation,
)
from projectkoios.ingestion.transcription.item import TranscriptionItem
from projectkoios.ingestion.transcription.omission import (
    TranscriptionOmission,
)
from projectkoios.ingestion.transcription.omission_reason import (
    TranscriptionOmissionReason,
)
from projectkoios.ingestion.transcription.order_status import (
    TranscriptionOrderStatus,
)
from projectkoios.ingestion.transcription.structured_request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.structured_result import (
    StructuredTranscriptionResult,
)


class DeterministicStructuredTranscriptionComposer(
    DataObjectActionizer[
        StructuredTranscriptionRequest, StructuredTranscriptionResult
    ]
):
    """Compose exact evidence into a destination-independent proposal."""

    __slots__ = ()

    name = "deterministic-structured-transcription-composer"
    version = AbstractTranscriptionDataObject.COMPOSER_VERSION

    def action(
        self, *, request: StructuredTranscriptionRequest
    ) -> StructuredTranscriptionResult:
        transcription_input = request
        if not isinstance(transcription_input, StructuredTranscriptionRequest):
            raise TypeError("request must be StructuredTranscriptionRequest")
        document = transcription_input.document
        block_by_id = {
            block.block_id: block
            for page in document.pages
            for block in page.blocks
        }
        block_position = {
            block.block_id: (page.page_index, index)
            for page in document.pages
            for index, block in enumerate(page.blocks)
        }
        page_label_by_index = {
            page.page_index: page.printed_page_label for page in document.pages
        }
        drafts: list[TranscriptionDerivation] = []
        omissions: list[TranscriptionOmission] = []
        warnings: list[IngestionWarning] = []
        claimed: dict[str, list[str]] = {}

        for page in document.pages:
            drafts.append(PageTranscriptionDerivation.derive(document, page))

        page_by_index = {page.page_index: page for page in document.pages}
        equation_drafts = [
            EquationTranscriptionDerivation.derive(
                candidate,
                page_by_index[
                    candidate.source_spans[0].page_index
                ].printed_page_label,
            )
            for candidate in (
                transcription_input.equation_detection_result.candidates
            )
        ]
        table_result = transcription_input.table_structure_result
        table_candidate_by_id = {
            candidate.candidate_id: candidate
            for candidate in (
                table_result.structure_input.detection_result.candidates
            )
        }
        table_drafts = [
            TableTranscriptionDerivation.derive(
                structure,
                table_candidate_by_id[structure.candidate_id],
                page_by_index[
                    min(
                        region.page_index
                        for region in table_candidate_by_id[
                            structure.candidate_id
                        ].regions
                    )
                ].printed_page_label,
            )
            for structure in table_result.structures
        ]
        figure_drafts = [
            FigureTranscriptionDerivation.derive(
                candidate,
                page_by_index[candidate.page_index].printed_page_label,
            )
            for candidate in (
                transcription_input.figure_detection_result.candidates
            )
        ]
        typed_drafts = equation_drafts + table_drafts + figure_drafts
        typed_draft_ids = tuple(draft.item_id for draft in typed_drafts)
        typed_item_ids = set(typed_draft_ids)
        for typed_draft, item_id in zip(
            typed_drafts, typed_draft_ids, strict=True
        ):
            drafts.append(typed_draft)
            for block_id in typed_draft.source_block_ids:
                claimed.setdefault(block_id, []).append(item_id)

        for block_id, item_ids in claimed.items():
            if len(item_ids) > 1:
                block = block_by_id[block_id]
                warnings.append(
                    IngestionWarning.create(
                        code="transcription.typed_source_overlap",
                        severity=WarningSeverity.WARNING,
                        message=(
                            "Multiple typed objects reference the same raw "
                            "block; all remain explicit proposals."
                        ),
                        object_ids=tuple(item_ids),
                        source_spans=block.source_spans,
                        evidence=(("source_block_id", block_id),),
                    )
                )

        nodes = sorted(
            transcription_input.structure_analysis.nodes,
            key=lambda node: (
                node.reading_order is None,
                node.reading_order if node.reading_order is not None else 0,
                node.node_id,
            ),
        )
        for node in nodes:
            disposition = TranscriptionStructureDisposition.derive(node)
            if disposition.item_kind is None:
                continue
            available: list[ExtractedBlock] = []
            for block_id in node.source_block_ids:
                block = block_by_id[block_id]
                represented = tuple(claimed.get(block_id, ()))
                if represented:
                    reason = (
                        TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT
                        if any(
                            item_id in typed_item_ids for item_id in represented
                        )
                        else (
                            TranscriptionOmissionReason.REPRESENTED_BY_EARLIER_ITEM
                        )
                    )
                    omissions.append(
                        TranscriptionOmission.create(
                            omitted_object_id=node.node_id,
                            source_block_id=block_id,
                            source_spans=block.source_spans,
                            reason=reason,
                            represented_by_item_ids=represented,
                        )
                    )
                elif block.text is None:
                    omissions.append(
                        TranscriptionOmission.create(
                            omitted_object_id=node.node_id,
                            source_block_id=block_id,
                            source_spans=block.source_spans,
                            reason=TranscriptionOmissionReason.NO_TEXT_PAYLOAD,
                        )
                    )
                else:
                    available.append(block)
            if available:
                structure_draft = StructureTranscriptionDerivation.derive(
                    node,
                    tuple(available),
                    page_label_by_index,
                    disposition,
                )
                drafts.append(structure_draft)
                item_id = structure_draft.item_id
                for block in available:
                    claimed.setdefault(block.block_id, []).append(item_id)

        for page in document.pages:
            for block in page.blocks:
                if block.block_id in claimed:
                    continue
                if block.text is not None:
                    raw_block_draft = RawBlockTranscriptionDerivation.derive(
                        page.page_index, page.printed_page_label, block
                    )
                    drafts.append(raw_block_draft)
                    claimed.setdefault(block.block_id, []).append(
                        raw_block_draft.item_id
                    )
                else:
                    omissions.append(
                        TranscriptionOmission.create(
                            omitted_object_id=block.block_id,
                            source_block_id=block.block_id,
                            source_spans=block.source_spans,
                            reason=(
                                TranscriptionOmissionReason.UNREPRESENTED_NON_TEXT_BLOCK
                            ),
                        )
                    )

        order_derivation_by_item_id = {
            draft.item_id: TranscriptionOrderDerivation.derive(
                draft, block_position
            )
            for draft in drafts
        }
        drafts.sort(
            key=lambda draft: (
                order_derivation_by_item_id[draft.item_id].order_key
            )
        )
        items: list[TranscriptionItem] = []
        for order_index, ordered_draft in enumerate(drafts):
            order_status = order_derivation_by_item_id[
                ordered_draft.item_id
            ].order_status
            item_warnings: list[IngestionWarning] = []
            for code in ordered_draft.warning_codes:
                item_warnings.append(
                    TranscriptionWarningDerivation.derive(
                        ordered_draft, code
                    ).warning
                )
            if order_status is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER:
                item_warnings.append(
                    TranscriptionWarningDerivation.derive(
                        ordered_draft, "transcription.order_uncertain"
                    ).warning
                )
            warnings.extend(item_warnings)
            items.append(
                TranscriptionItem.create(
                    item_kind=ordered_draft.item_kind,
                    source_object_kind=ordered_draft.source_object_kind,
                    source_object_id=ordered_draft.source_object_id,
                    page_index=ordered_draft.page_index,
                    printed_page_label=ordered_draft.printed_page_label,
                    order_index=order_index,
                    order_status=order_status,
                    evidence_status=ordered_draft.evidence_status,
                    confidence=ordered_draft.confidence,
                    source_block_ids=ordered_draft.source_block_ids,
                    source_spans=ordered_draft.source_spans,
                    source_texts=ordered_draft.source_texts,
                    warning_ids=tuple(
                        warning.warning_id for warning in item_warnings
                    ),
                    evidence=ordered_draft.evidence,
                )
            )

        result = StructuredTranscriptionResult.create(
            transcription_input=transcription_input,
            items=tuple(items),
            omissions=tuple(omissions),
            warnings=AbstractTranscriptionDataObject.deduplicate_warnings(
                tuple(warnings)
            ),
            processor_name=self.name,
            processor_version=self.version,
        )
        return result
