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
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.item_kind import (
    TranscriptionItemKind,
)
from projectkoios.ingestion.transcription.omission.omission import (
    TranscriptionOmission,
)
from projectkoios.ingestion.transcription.omission_reason import (
    TranscriptionOmissionReason,
)
from projectkoios.ingestion.transcription.order.status import (
    TranscriptionOrderStatus,
)
from projectkoios.ingestion.transcription.request.request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.result.result import (
    StructuredTranscriptionResult,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


class DeterministicStructuredTranscriptionComposer(
    DataObjectActionizer[
        StructuredTranscriptionRequest, StructuredTranscriptionResult
    ]
):
    """Compose exact evidence into a destination-independent proposal."""

    __slots__ = ()

    _page_anchor_draft = staticmethod(
        TranscriptionDerivation._page_anchor_draft
    )
    _structure_draft = staticmethod(TranscriptionDerivation._structure_draft)
    _raw_block_draft = staticmethod(TranscriptionDerivation._raw_block_draft)
    _item_kind_for_node = staticmethod(
        TranscriptionDerivation._item_kind_for_node
    )
    _draft_order_key = staticmethod(TranscriptionDerivation._draft_order_key)
    _draft_order_status = staticmethod(
        TranscriptionDerivation._draft_order_status
    )
    _draft_warning = staticmethod(TranscriptionDerivation._draft_warning)
    _table_projection = staticmethod(TranscriptionDerivation._table_projection)
    _figure_projection = staticmethod(
        TranscriptionDerivation._figure_projection
    )
    _equation_status = staticmethod(TranscriptionDerivation._equation_status)
    _table_status = staticmethod(TranscriptionDerivation._table_status)
    _figure_status = staticmethod(TranscriptionDerivation._figure_status)
    _structure_status = staticmethod(TranscriptionDerivation._structure_status)

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
            drafts.append(self._page_anchor_draft(document, page))

        typed_drafts = (
            self._equation_drafts(transcription_input)
            + self._table_drafts(transcription_input)
            + self._figure_drafts(transcription_input)
        )
        typed_draft_ids = tuple(draft.item_id for draft in typed_drafts)
        typed_item_ids = set(typed_draft_ids)
        for draft, item_id in zip(typed_drafts, typed_draft_ids, strict=True):
            drafts.append(draft)
            for block_id in draft.source_block_ids:
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
            item_kind = self._item_kind_for_node(node)
            if item_kind is None:
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
                draft = self._structure_draft(
                    node,
                    tuple(available),
                    item_kind,
                    page_label_by_index,
                )
                drafts.append(draft)
                item_id = draft.item_id
                for block in available:
                    claimed.setdefault(block.block_id, []).append(item_id)

        for page in document.pages:
            for block in page.blocks:
                if block.block_id in claimed:
                    continue
                if block.text is not None:
                    draft = self._raw_block_draft(
                        page.page_index, page.printed_page_label, block
                    )
                    drafts.append(draft)
                    claimed.setdefault(block.block_id, []).append(draft.item_id)
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

        drafts.sort(
            key=lambda draft: self._draft_order_key(draft, block_position)
        )
        items: list[TranscriptionItem] = []
        for order_index, draft in enumerate(drafts):
            order_status = self._draft_order_status(draft)
            item_warnings: list[IngestionWarning] = []
            for code in draft.warning_codes:
                item_warnings.append(self._draft_warning(draft, code))
            if order_status is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER:
                item_warnings.append(
                    self._draft_warning(draft, "transcription.order_uncertain")
                )
            warnings.extend(item_warnings)
            items.append(
                TranscriptionItem.create(
                    item_kind=draft.item_kind,
                    source_object_kind=draft.source_object_kind,
                    source_object_id=draft.source_object_id,
                    page_index=draft.page_index,
                    printed_page_label=draft.printed_page_label,
                    order_index=order_index,
                    order_status=order_status,
                    evidence_status=draft.evidence_status,
                    confidence=draft.confidence,
                    source_block_ids=draft.source_block_ids,
                    source_spans=draft.source_spans,
                    source_texts=draft.source_texts,
                    warning_ids=tuple(
                        warning.warning_id for warning in item_warnings
                    ),
                    evidence=draft.evidence,
                )
            )

        result = StructuredTranscriptionResult.create(
            transcription_input=transcription_input,
            items=tuple(items),
            omissions=tuple(omissions),
            warnings=AbstractTranscriptionDataObject._deduplicate_warnings(
                tuple(warnings)
            ),
            processor_name=self.name,
            processor_version=self.version,
        )
        return result

    @staticmethod
    def _equation_drafts(
        transcription_input: StructuredTranscriptionRequest,
    ) -> list[TranscriptionDerivation]:
        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        result: list[TranscriptionDerivation] = []
        for (
            candidate
        ) in transcription_input.equation_detection_result.candidates:
            page_index = candidate.source_spans[0].page_index
            result.append(
                TranscriptionDerivation(
                    item_kind=TranscriptionItemKind.EQUATION,
                    source_object_kind=(
                        TranscriptionSourceObjectKind.EQUATION_CANDIDATE
                    ),
                    source_object_id=candidate.candidate_id,
                    page_index=page_index,
                    printed_page_label=page_by_index[
                        page_index
                    ].printed_page_label,
                    source_block_ids=(candidate.source_block_id,),
                    source_spans=candidate.source_spans,
                    source_texts=(candidate.raw_text,),
                    evidence_status=TranscriptionDerivation._equation_status(
                        candidate
                    ),
                    confidence=candidate.confidence,
                    structure_reading_order=None,
                    evidence=(("candidate_kind", candidate.kind.value),),
                )
            )
        return result

    @staticmethod
    def _table_drafts(
        transcription_input: StructuredTranscriptionRequest,
    ) -> list[TranscriptionDerivation]:
        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        structure_result = transcription_input.table_structure_result
        detection = structure_result.structure_input.detection_result
        candidate_by_id = {
            candidate.candidate_id: candidate
            for candidate in detection.candidates
        }
        result: list[TranscriptionDerivation] = []
        for structure in structure_result.structures:
            candidate = candidate_by_id[structure.candidate_id]
            block_ids, spans = TranscriptionDerivation._table_projection(
                structure, candidate
            )
            page_index = min(region.page_index for region in candidate.regions)
            result.append(
                TranscriptionDerivation(
                    item_kind=TranscriptionItemKind.TABLE,
                    source_object_kind=TranscriptionSourceObjectKind.TABLE_STRUCTURE,
                    source_object_id=structure.structure_id,
                    page_index=page_index,
                    printed_page_label=page_by_index[
                        page_index
                    ].printed_page_label,
                    source_block_ids=block_ids,
                    source_spans=spans,
                    source_texts=(),
                    evidence_status=TranscriptionDerivation._table_status(
                        structure
                    ),
                    confidence=structure.confidence,
                    structure_reading_order=None,
                    evidence=(("candidate_id", candidate.candidate_id),),
                )
            )
        return result

    @staticmethod
    def _figure_drafts(
        transcription_input: StructuredTranscriptionRequest,
    ) -> list[TranscriptionDerivation]:
        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        result: list[TranscriptionDerivation] = []
        for candidate in transcription_input.figure_detection_result.candidates:
            block_ids, spans = TranscriptionDerivation._figure_projection(
                candidate
            )
            result.append(
                TranscriptionDerivation(
                    item_kind=TranscriptionItemKind.FIGURE,
                    source_object_kind=TranscriptionSourceObjectKind.FIGURE_CANDIDATE,
                    source_object_id=candidate.candidate_id,
                    page_index=candidate.page_index,
                    printed_page_label=page_by_index[
                        candidate.page_index
                    ].printed_page_label,
                    source_block_ids=block_ids,
                    source_spans=spans,
                    source_texts=(),
                    evidence_status=TranscriptionDerivation._figure_status(
                        candidate
                    ),
                    confidence=candidate.confidence,
                    structure_reading_order=None,
                    evidence=(
                        ("component_count", str(len(candidate.components))),
                    ),
                )
            )
        return result

    def compose(
        self, transcription_input: StructuredTranscriptionRequest
    ) -> StructuredTranscriptionResult:
        """Compose one request through the canonical action path."""
        return self.action(request=transcription_input)
