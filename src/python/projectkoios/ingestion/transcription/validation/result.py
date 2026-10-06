from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.validation import AbstractValidation
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import IngestionWarning
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.cache.identity import (
    TranscriptionCacheIdentity,
)
from projectkoios.ingestion.transcription.derivation.disposition.structure import (  # noqa: E501
    TranscriptionStructureDisposition,
)
from projectkoios.ingestion.transcription.derivation.order import (
    TranscriptionOrderDerivation,
)
from projectkoios.ingestion.transcription.derivation.page import (
    PageTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.item import TranscriptionItem
from projectkoios.ingestion.transcription.kind.item import TranscriptionItemKind
from projectkoios.ingestion.transcription.kind.source.object import (
    TranscriptionSourceObjectKind,
)
from projectkoios.ingestion.transcription.limits.error import (
    TranscriptionLimitError,
)
from projectkoios.ingestion.transcription.omission import TranscriptionOmission
from projectkoios.ingestion.transcription.reason.omission import (
    TranscriptionOmissionReason,
)
from projectkoios.ingestion.transcription.request.structured import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.status.order import (
    TranscriptionOrderStatus,
)
from projectkoios.ingestion.transcription.status.result import (
    TranscriptionStatus,
)


@dataclass(frozen=True)
class TranscriptionResultValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    validation_id: str
    result_id: str
    request_id: str
    item_set_id: str
    omission_set_id: str
    warning_set_id: str
    validated_item_count: int
    validated_omission_count: int
    validated_warning_count: int
    validated_source_span_count: int
    validated_text_characters: int
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def validate(
        cls,
        *,
        result_id: str,
        transcription_input: StructuredTranscriptionRequest,
        items: tuple[TranscriptionItem, ...],
        omissions: tuple[TranscriptionOmission, ...],
        warnings: tuple[IngestionWarning, ...],
        status: TranscriptionStatus,
        processor_name: str,
        processor_version: str,
        configuration_digest: str,
        cache_key: str,
    ) -> TranscriptionResultValidation:
        cls.validate_tuple("transcription items", items)
        cls.validate_tuple("transcription omissions", omissions)
        cls.validate_tuple("transcription warnings", warnings)
        if any(not isinstance(item, TranscriptionItem) for item in items):
            raise TypeError("transcription items contain an unsupported value")
        if any(
            not isinstance(item, TranscriptionOmission) for item in omissions
        ):
            raise TypeError(
                "transcription omissions contain an unsupported value"
            )
        if any(not isinstance(item, IngestionWarning) for item in warnings):
            raise TypeError(
                "transcription warnings contain an unsupported value"
            )
        cls.validate_identity_fields(
            result_id, processor_name, processor_version
        )

        configuration = transcription_input.configuration
        if configuration_digest != configuration.configuration_digest:
            raise ValueError(
                "transcription configuration digest is inconsistent"
            )
        expected_cache = TranscriptionCacheIdentity.create(
            transcription_input,
            processor_name=processor_name,
            processor_version=processor_version,
        ).cache_key
        if cache_key != expected_cache:
            raise ValueError("transcription cache key is inconsistent")
        if status is not TranscriptionStatus.determine(
            items, omissions, warnings
        ):
            raise ValueError("transcription status is inconsistent")

        item_ids = tuple(item.item_id for item in items)
        omission_ids = tuple(omission.omission_id for omission in omissions)
        warning_ids = tuple(warning.warning_id for warning in warnings)
        cls.validate_unique_strings("transcription item IDs", item_ids)
        cls.validate_unique_strings("transcription omission IDs", omission_ids)
        cls.validate_unique_strings("transcription warning IDs", warning_ids)
        if tuple(item.order_index for item in items) != tuple(
            range(len(items))
        ):
            raise ValueError(
                "transcription item order indices are inconsistent"
            )
        source_keys = tuple(
            (item.source_object_kind, item.source_object_id) for item in items
        )
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("transcription source objects must be unique")
        omission_keys = tuple(
            (omission.omitted_object_id, omission.source_block_id)
            for omission in omissions
        )
        if len(set(omission_keys)) != len(omission_keys):
            raise ValueError("transcription omission sources must be unique")

        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        block_by_id = {
            block.block_id: block
            for page in document.pages
            for block in page.blocks
        }
        node_by_id = {
            node.node_id: node
            for node in transcription_input.structure_analysis.nodes
        }
        valid_source_ids = {
            TranscriptionSourceObjectKind.PAGE: {
                PageTranscriptionDerivation.source_object_identity(
                    document, page
                )
                for page in document.pages
            },
            TranscriptionSourceObjectKind.RAW_BLOCK: set(block_by_id),
            TranscriptionSourceObjectKind.STRUCTURE_NODE: set(node_by_id),
            TranscriptionSourceObjectKind.EQUATION_CANDIDATE: {
                candidate.candidate_id
                for candidate in (
                    transcription_input.equation_detection_result.candidates
                )
            },
            TranscriptionSourceObjectKind.TABLE_STRUCTURE: {
                structure.structure_id
                for structure in (
                    transcription_input.table_structure_result.structures
                )
            },
            TranscriptionSourceObjectKind.FIGURE_CANDIDATE: {
                candidate.candidate_id
                for candidate in (
                    transcription_input.figure_detection_result.candidates
                )
            },
        }
        warning_by_id = {warning.warning_id: warning for warning in warnings}
        for item in items:
            page = page_by_index.get(item.page_index)
            if (
                page is None
                or item.printed_page_label != page.printed_page_label
            ):
                raise ValueError("transcription item page is unresolved")
            if (
                item.source_object_id
                not in valid_source_ids[item.source_object_kind]
            ):
                raise ValueError(
                    "transcription item source object is unresolved"
                )
            if not set(item.source_block_ids).issubset(block_by_id):
                raise ValueError(
                    "transcription item source block is unresolved"
                )
            cls.validate_exact_source_spans(item.source_spans, document)
            if not set(item.warning_ids).issubset(warning_by_id):
                raise ValueError(
                    "transcription item warning link is unresolved"
                )
            structure_node = (
                node_by_id[item.source_object_id]
                if item.source_object_kind
                is TranscriptionSourceObjectKind.STRUCTURE_NODE
                else None
            )
            expected_order_status = TranscriptionOrderDerivation.status_for(
                item.item_kind,
                item.page_index,
                item.source_spans,
                (
                    structure_node.reading_order
                    if structure_node is not None
                    else None
                ),
            )
            if item.order_status is not expected_order_status:
                raise ValueError(
                    "transcription item order evidence is inconsistent"
                )
            if expected_order_status is (
                TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER
            ) and "transcription.order_uncertain" not in {
                warning_by_id[value].code for value in item.warning_ids
            }:
                raise ValueError("uncertain order lacks a warning")

        item_by_id = {item.item_id: item for item in items}
        typed_source_kinds = {
            TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
            TranscriptionSourceObjectKind.TABLE_STRUCTURE,
            TranscriptionSourceObjectKind.FIGURE_CANDIDATE,
        }
        for omission in omissions:
            block = block_by_id.get(omission.source_block_id)
            if block is None or omission.source_spans != block.source_spans:
                raise ValueError("transcription omission source is unresolved")
            if omission.omitted_object_id != block.block_id:
                omitted_node = node_by_id.get(omission.omitted_object_id)
                if (
                    omitted_node is None
                    or block.block_id not in omitted_node.source_block_ids
                ):
                    raise ValueError(
                        "transcription omitted object is unresolved"
                    )
            if not set(omission.warning_ids).issubset(warning_by_id):
                raise ValueError(
                    "transcription omission warning link is unresolved"
                )
            if not set(omission.represented_by_item_ids).issubset(item_by_id):
                raise ValueError(
                    "transcription omission item link is unresolved"
                )
            linked_items = tuple(
                item_by_id[item_id]
                for item_id in omission.represented_by_item_ids
            )
            if any(
                block.block_id not in item.source_block_ids
                for item in linked_items
            ):
                raise ValueError(
                    "transcription omission replacement is unresolved"
                )
            if (
                omission.reason
                is TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT
            ):
                if not any(
                    item.source_object_kind in typed_source_kinds
                    for item in linked_items
                ):
                    raise ValueError("typed omission lacks a typed replacement")
            if (
                omission.reason
                is TranscriptionOmissionReason.REPRESENTED_BY_EARLIER_ITEM
                and any(
                    item.source_object_kind in typed_source_kinds
                    for item in linked_items
                )
            ):
                raise ValueError(
                    "earlier-item omission has a typed replacement"
                )
            if (
                omission.reason
                in (
                    TranscriptionOmissionReason.NO_TEXT_PAYLOAD,
                    TranscriptionOmissionReason.UNREPRESENTED_NON_TEXT_BLOCK,
                )
                and block.text is not None
            ):
                raise ValueError("non-text omission refers to a text block")
            if (
                omission.reason
                is TranscriptionOmissionReason.UNREPRESENTED_NON_TEXT_BLOCK
                and omission.omitted_object_id != block.block_id
            ):
                raise ValueError(
                    "unrepresented omission must identify its block"
                )

        expected_page_indices = tuple(
            page.page_index for page in document.pages
        )
        actual_page_indices = tuple(
            item.page_index
            for item in items
            if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR
        )
        if actual_page_indices != expected_page_indices:
            raise ValueError("transcription page anchors are incomplete")
        for source_kind in typed_source_kinds:
            actual_ids = {
                item.source_object_id
                for item in items
                if item.source_object_kind is source_kind
            }
            if actual_ids != valid_source_ids[source_kind]:
                raise ValueError(
                    "transcription typed-object coverage is incomplete"
                )
        represented_node_ids = {
            item.source_object_id
            for item in items
            if item.source_object_kind
            is TranscriptionSourceObjectKind.STRUCTURE_NODE
        } | {omission.omitted_object_id for omission in omissions}
        expected_node_ids = {
            node.node_id
            for node in transcription_input.structure_analysis.nodes
            if node.source_block_ids
            and TranscriptionStructureDisposition.item_kind_for(node.kind)
            is not None
        }
        if not expected_node_ids.issubset(represented_node_ids):
            raise ValueError(
                "transcription structure-node coverage is incomplete"
            )
        represented_blocks = {
            block_id for item in items for block_id in item.source_block_ids
        } | {omission.source_block_id for omission in omissions}
        if represented_blocks != set(block_by_id):
            raise ValueError("transcription raw block coverage is incomplete")

        valid_warning_object_ids = (
            set(item_ids)
            | {item.source_object_id for item in items}
            | set(omission_ids)
            | {omission.source_block_id for omission in omissions}
        )
        for warning in warnings:
            if not set(warning.object_ids).issubset(valid_warning_object_ids):
                raise ValueError("transcription warning object is unresolved")
            cls.validate_exact_source_spans(warning.source_spans, document)

        if len(items) > configuration.max_items:
            raise TranscriptionLimitError("items exceed max_items")
        if len(omissions) > configuration.max_omissions:
            raise TranscriptionLimitError("omissions exceed max_omissions")
        if len(warnings) > configuration.max_warnings:
            raise TranscriptionLimitError("warnings exceed max_warnings")
        source_span_count = sum(len(item.source_spans) for item in items) + sum(
            len(omission.source_spans) for omission in omissions
        )
        if source_span_count > configuration.max_source_spans:
            raise TranscriptionLimitError(
                "source spans exceed max_source_spans"
            )
        text_lengths = tuple(
            len(item.normalized_text or "")
            + sum(len(text) for text in item.source_texts)
            for item in items
        )
        if any(
            length > configuration.max_text_characters_per_item
            for length in text_lengths
        ):
            raise TranscriptionLimitError(
                "item text exceeds max_text_characters_per_item"
            )
        text_characters = sum(text_lengths)
        if text_characters > configuration.max_total_text_characters:
            raise TranscriptionLimitError(
                "text exceeds max_total_text_characters"
            )
        cls.validate_retained_size(
            (result_id, transcription_input, items, omissions, warnings),
            configuration.max_result_bytes,
        )

        item_set_id = stable_id("transcription-item-set", item_ids)
        omission_set_id = stable_id("transcription-omission-set", omission_ids)
        warning_set_id = stable_id("transcription-warning-set", warning_ids)
        identity_parts = (
            result_id,
            transcription_input.input_id,
            item_set_id,
            omission_set_id,
            warning_set_id,
            len(items),
            len(omissions),
            len(warnings),
            source_span_count,
            text_characters,
        )
        return cls(
            validation_id=stable_id(
                "transcription-result-validation", *identity_parts
            ),
            result_id=result_id,
            request_id=transcription_input.input_id,
            item_set_id=item_set_id,
            omission_set_id=omission_set_id,
            warning_set_id=warning_set_id,
            validated_item_count=len(items),
            validated_omission_count=len(omissions),
            validated_warning_count=len(warnings),
            validated_source_span_count=source_span_count,
            validated_text_characters=text_characters,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription result validation version"
            )
        self.validate_identity_fields(
            self.validation_id,
            self.result_id,
            self.request_id,
            self.item_set_id,
            self.omission_set_id,
            self.warning_set_id,
        )
        for name, value in (
            ("validated item count", self.validated_item_count),
            ("validated omission count", self.validated_omission_count),
            ("validated warning count", self.validated_warning_count),
            ("validated source-span count", self.validated_source_span_count),
            ("validated text characters", self.validated_text_characters),
        ):
            self.validate_nonnegative_integer(name, value)
        expected = stable_id(
            "transcription-result-validation",
            self.result_id,
            self.request_id,
            self.item_set_id,
            self.omission_set_id,
            self.warning_set_id,
            self.validated_item_count,
            self.validated_omission_count,
            self.validated_warning_count,
            self.validated_source_span_count,
            self.validated_text_characters,
        )
        if self.validation_id != expected:
            raise ValueError(
                "transcription result validation ID is inconsistent"
            )
