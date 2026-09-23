from __future__ import annotations

import math
import re
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, StrEnum

from projectkoios.ingestion.base import BaseStructuredTranscriptionComposer
from projectkoios.ingestion.equations import (
    EquationCandidate,
    EquationDetectionResult,
    EquationEvidenceStatus,
)
from projectkoios.ingestion.figures import (
    EmbeddedFigureArtifact,
    FigureCandidate,
    FigureDetectionResult,
    FigureEvidenceStatus,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    IngestionWarning,
    Metadata,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.models import RenderedRegion
from projectkoios.ingestion.structure import (
    StructureAnalysis,
    StructureEvidenceStatus,
    StructureKind,
    StructureNode,
)
from projectkoios.ingestion.table_structure import (
    TableStructure,
    TableStructureEvidenceStatus,
    TableStructureResult,
)
from projectkoios.ingestion.tables import TableCandidate

TRANSCRIPTION_CONTRACT_VERSION = "1.0"
TRANSCRIPTION_COMPOSER_VERSION = "1"
TRANSCRIPTION_CONFIGURATION_VERSION = "1"
TRANSCRIPTION_NORMALIZATION_METHOD = "collapse_unicode_whitespace_v1"
_MAX_INPUT_BLOCKS = 65_536
_MAX_INPUT_NODES = 16_384
_MAX_TYPED_OBJECTS = 16_384
_MAX_ITEMS = 65_536
_MAX_OMISSIONS = 65_536
_MAX_WARNINGS = 16_384
_MAX_SOURCE_SPANS = 262_144
_MAX_TEXT_CHARACTERS_PER_ITEM = 1_000_000
_MAX_TOTAL_TEXT_CHARACTERS = 10_000_000
_MAX_INPUT_ARTIFACT_BYTES = 100_000_000
_MAX_RESULT_BYTES = 128_000_000
_MAX_IDENTITY_CHARACTERS = 4_096
_MAX_EVIDENCE_ENTRIES = 256
_MAX_EVIDENCE_CHARACTERS = 1_000_000
_WHITESPACE = re.compile(r"\s+")


class TranscriptionLimitError(ValueError):
    """Raised before transcription composition exceeds a hard bound."""


class TranscriptionItemKind(StrEnum):
    PAGE_ANCHOR = "page_anchor"
    HEADING = "heading"
    PROSE = "prose"
    EQUATION = "equation"
    TABLE = "table"
    FIGURE = "figure"


class TranscriptionSourceObjectKind(StrEnum):
    PAGE = "page"
    RAW_BLOCK = "raw_block"
    STRUCTURE_NODE = "structure_node"
    EQUATION_CANDIDATE = "equation_candidate"
    TABLE_STRUCTURE = "table_structure"
    FIGURE_CANDIDATE = "figure_candidate"


class TranscriptionEvidenceStatus(StrEnum):
    OBSERVED_SOURCE_TRANSFORM = "observed_source_transform"
    PROPOSED = "proposed"
    AMBIGUOUS = "ambiguous"


class TranscriptionOrderStatus(StrEnum):
    PAGE_ANCHOR = "page_anchor"
    PROPOSED_GEOMETRIC = "proposed_geometric"
    PROPOSED_STRUCTURE = "proposed_structure"
    UNCERTAIN_SOURCE_ORDER = "uncertain_source_order"


class TranscriptionOmissionReason(StrEnum):
    REPRESENTED_BY_TYPED_OBJECT = "represented_by_typed_object"
    REPRESENTED_BY_EARLIER_ITEM = "represented_by_earlier_item"
    NO_TEXT_PAYLOAD = "no_text_payload"
    UNREPRESENTED_NON_TEXT_BLOCK = "unrepresented_non_text_block"


class TranscriptionStatus(StrEnum):
    PROPOSED = "proposed"
    PROPOSED_WITH_UNCERTAINTY = "proposed_with_uncertainty"


@dataclass(frozen=True)
class TranscriptionConfiguration:
    configuration_version: str = TRANSCRIPTION_CONFIGURATION_VERSION
    normalization_method: str = TRANSCRIPTION_NORMALIZATION_METHOD
    max_input_blocks: int = _MAX_INPUT_BLOCKS
    max_input_nodes: int = _MAX_INPUT_NODES
    max_typed_objects: int = _MAX_TYPED_OBJECTS
    max_items: int = _MAX_ITEMS
    max_omissions: int = _MAX_OMISSIONS
    max_warnings: int = _MAX_WARNINGS
    max_source_spans: int = _MAX_SOURCE_SPANS
    max_text_characters_per_item: int = _MAX_TEXT_CHARACTERS_PER_ITEM
    max_total_text_characters: int = _MAX_TOTAL_TEXT_CHARACTERS
    max_input_artifact_bytes: int = _MAX_INPUT_ARTIFACT_BYTES
    max_result_bytes: int = _MAX_RESULT_BYTES

    def __post_init__(self) -> None:
        if self.configuration_version != TRANSCRIPTION_CONFIGURATION_VERSION:
            raise ValueError("unsupported transcription configuration version")
        if self.normalization_method != TRANSCRIPTION_NORMALIZATION_METHOD:
            raise ValueError("unsupported transcription normalization method")
        for name, hard_limit in (
            ("max_input_blocks", _MAX_INPUT_BLOCKS),
            ("max_input_nodes", _MAX_INPUT_NODES),
            ("max_typed_objects", _MAX_TYPED_OBJECTS),
            ("max_items", _MAX_ITEMS),
            ("max_omissions", _MAX_OMISSIONS),
            ("max_warnings", _MAX_WARNINGS),
            ("max_source_spans", _MAX_SOURCE_SPANS),
            (
                "max_text_characters_per_item",
                _MAX_TEXT_CHARACTERS_PER_ITEM,
            ),
            ("max_total_text_characters", _MAX_TOTAL_TEXT_CHARACTERS),
            ("max_input_artifact_bytes", _MAX_INPUT_ARTIFACT_BYTES),
            ("max_result_bytes", _MAX_RESULT_BYTES),
        ):
            value = getattr(self, name)
            _positive_integer(name, value)
            if value > hard_limit:
                raise TranscriptionLimitError(
                    f"{name} exceeds its implementation maximum ({hard_limit})"
                )

    @property
    def configuration_digest(self) -> str:
        return stable_id("transcription-configuration", self.identity_parts())

    def identity_parts(self) -> tuple[object, ...]:
        return tuple(
            (name, getattr(self, name)) for name in self.__dataclass_fields__
        )


@dataclass(frozen=True)
class TranscriptionInput:
    input_id: str
    document_evidence_id: str
    document: ExtractedDocument
    structure_analysis: StructureAnalysis
    equation_detection_result: EquationDetectionResult
    table_structure_result: TableStructureResult
    figure_detection_result: FigureDetectionResult
    configuration: TranscriptionConfiguration
    contract_version: str = TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        document: ExtractedDocument,
        structure_analysis: StructureAnalysis,
        equation_detection_result: EquationDetectionResult,
        table_structure_result: TableStructureResult,
        figure_detection_result: FigureDetectionResult,
        configuration: TranscriptionConfiguration | None = None,
    ) -> TranscriptionInput:
        actual = configuration or TranscriptionConfiguration()
        _validate_input_parts(
            document,
            structure_analysis,
            equation_detection_result,
            table_structure_result,
            figure_detection_result,
            actual,
        )
        document_evidence_id = _document_evidence_id(document)
        return cls(
            input_id=_input_id(
                document_evidence_id,
                document,
                structure_analysis,
                equation_detection_result,
                table_structure_result,
                figure_detection_result,
                actual,
            ),
            document_evidence_id=document_evidence_id,
            document=document,
            structure_analysis=structure_analysis,
            equation_detection_result=equation_detection_result,
            table_structure_result=table_structure_result,
            figure_detection_result=figure_detection_result,
            configuration=actual,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription input version")
        _validate_input_parts(
            self.document,
            self.structure_analysis,
            self.equation_detection_result,
            self.table_structure_result,
            self.figure_detection_result,
            self.configuration,
        )
        _identity_fields(self.document_evidence_id)
        expected_document_evidence_id = _document_evidence_id(self.document)
        if self.document_evidence_id != expected_document_evidence_id:
            raise ValueError(
                "transcription document evidence ID is inconsistent"
            )
        expected = _input_id(
            self.document_evidence_id,
            self.document,
            self.structure_analysis,
            self.equation_detection_result,
            self.table_structure_result,
            self.figure_detection_result,
            self.configuration,
        )
        if self.input_id != expected:
            raise ValueError("transcription input ID is inconsistent")


@dataclass(frozen=True)
class TranscriptionItem:
    item_id: str
    item_kind: TranscriptionItemKind
    source_object_kind: TranscriptionSourceObjectKind
    source_object_id: str
    page_index: int
    printed_page_label: str | None
    order_index: int
    order_status: TranscriptionOrderStatus
    evidence_status: TranscriptionEvidenceStatus
    confidence: float | None
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    normalized_text: str | None
    source_texts: tuple[str, ...]
    normalization_method: str | None
    warning_ids: tuple[str, ...] = ()
    evidence: Metadata = ()
    contract_version: str = TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        item_kind: TranscriptionItemKind,
        source_object_kind: TranscriptionSourceObjectKind,
        source_object_id: str,
        page_index: int,
        printed_page_label: str | None,
        order_index: int,
        order_status: TranscriptionOrderStatus,
        evidence_status: TranscriptionEvidenceStatus,
        confidence: float | None,
        source_block_ids: tuple[str, ...],
        source_spans: tuple[SourceSpan, ...],
        source_texts: tuple[str, ...] = (),
        warning_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
    ) -> TranscriptionItem:
        normalized_text = (
            _normalize_text(source_texts) if source_texts else None
        )
        method = TRANSCRIPTION_NORMALIZATION_METHOD if source_texts else None
        return cls(
            item_id=_item_id(
                item_kind,
                source_object_kind,
                source_object_id,
                page_index,
                source_block_ids,
                source_spans,
                normalized_text,
                source_texts,
                method,
                evidence_status,
                confidence,
                evidence,
            ),
            item_kind=item_kind,
            source_object_kind=source_object_kind,
            source_object_id=source_object_id,
            page_index=page_index,
            printed_page_label=printed_page_label,
            order_index=order_index,
            order_status=order_status,
            evidence_status=evidence_status,
            confidence=confidence,
            source_block_ids=source_block_ids,
            source_spans=source_spans,
            normalized_text=normalized_text,
            source_texts=source_texts,
            normalization_method=method,
            warning_ids=warning_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription item version")
        if not isinstance(self.item_kind, TranscriptionItemKind):
            raise TypeError("transcription item kind is unsupported")
        if not isinstance(
            self.source_object_kind, TranscriptionSourceObjectKind
        ):
            raise TypeError("transcription source-object kind is unsupported")
        _identity_fields(self.source_object_id)
        _nonnegative_integer("item page index", self.page_index)
        _nonnegative_integer("item order index", self.order_index)
        if self.printed_page_label is not None:
            _bounded_string("printed page label", self.printed_page_label)
        if not isinstance(self.order_status, TranscriptionOrderStatus):
            raise TypeError("transcription order status is unsupported")
        if not isinstance(self.evidence_status, TranscriptionEvidenceStatus):
            raise TypeError("transcription evidence status is unsupported")
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                _unit_float("item confidence", self.confidence),
            )
        _unique_strings("item source block IDs", self.source_block_ids)
        _validate_spans(self.source_spans)
        _require_tuple("source texts", self.source_texts)
        for text in self.source_texts:
            _bounded_string(
                "source text",
                text,
                limit=_MAX_TEXT_CHARACTERS_PER_ITEM,
            )
        if self.source_texts:
            if self.normalization_method != TRANSCRIPTION_NORMALIZATION_METHOD:
                raise ValueError(
                    "text item normalization method is inconsistent"
                )
            if self.normalized_text != _normalize_text(self.source_texts):
                raise ValueError("normalized text is inconsistent")
            assert self.normalized_text is not None
            _bounded_string(
                "normalized text",
                self.normalized_text,
                limit=_MAX_TEXT_CHARACTERS_PER_ITEM,
            )
        elif (
            self.normalized_text is not None
            or self.normalization_method is not None
        ):
            raise ValueError("text-free item cannot contain normalized text")
        _unique_strings("item warning IDs", self.warning_ids)
        _validate_metadata(self.evidence)
        expected = _item_id(
            self.item_kind,
            self.source_object_kind,
            self.source_object_id,
            self.page_index,
            self.source_block_ids,
            self.source_spans,
            self.normalized_text,
            self.source_texts,
            self.normalization_method,
            self.evidence_status,
            self.confidence,
            self.evidence,
        )
        if self.item_id != expected:
            raise ValueError("transcription item ID is inconsistent")


@dataclass(frozen=True)
class TranscriptionOmission:
    omission_id: str
    omitted_object_id: str
    source_block_id: str
    source_spans: tuple[SourceSpan, ...]
    reason: TranscriptionOmissionReason
    represented_by_item_ids: tuple[str, ...]
    warning_ids: tuple[str, ...] = ()
    evidence: Metadata = ()
    contract_version: str = TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        omitted_object_id: str,
        source_block_id: str,
        source_spans: tuple[SourceSpan, ...],
        reason: TranscriptionOmissionReason,
        represented_by_item_ids: tuple[str, ...] = (),
        warning_ids: tuple[str, ...] = (),
        evidence: Metadata = (),
    ) -> TranscriptionOmission:
        return cls(
            omission_id=_omission_id(
                omitted_object_id,
                source_block_id,
                source_spans,
                reason,
                represented_by_item_ids,
                evidence,
            ),
            omitted_object_id=omitted_object_id,
            source_block_id=source_block_id,
            source_spans=source_spans,
            reason=reason,
            represented_by_item_ids=represented_by_item_ids,
            warning_ids=warning_ids,
            evidence=evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported transcription omission version")
        _identity_fields(self.omitted_object_id, self.source_block_id)
        _validate_spans(self.source_spans)
        if not isinstance(self.reason, TranscriptionOmissionReason):
            raise TypeError("transcription omission reason is unsupported")
        _unique_strings("represented item IDs", self.represented_by_item_ids)
        _unique_strings("omission warning IDs", self.warning_ids)
        _validate_metadata(self.evidence)
        represented_reason = self.reason in (
            TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT,
            TranscriptionOmissionReason.REPRESENTED_BY_EARLIER_ITEM,
        )
        if represented_reason != bool(self.represented_by_item_ids):
            raise ValueError("omission representation links are inconsistent")
        expected = _omission_id(
            self.omitted_object_id,
            self.source_block_id,
            self.source_spans,
            self.reason,
            self.represented_by_item_ids,
            self.evidence,
        )
        if self.omission_id != expected:
            raise ValueError("transcription omission ID is inconsistent")


@dataclass(frozen=True)
class StructuredTranscriptionResult:
    result_id: str
    transcription_input: TranscriptionInput
    items: tuple[TranscriptionItem, ...]
    omissions: tuple[TranscriptionOmission, ...]
    warnings: tuple[IngestionWarning, ...]
    status: TranscriptionStatus
    processor_name: str
    processor_version: str
    configuration_digest: str
    cache_key: str
    contract_version: str = TRANSCRIPTION_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        transcription_input: TranscriptionInput,
        items: tuple[TranscriptionItem, ...],
        omissions: tuple[TranscriptionOmission, ...],
        warnings: tuple[IngestionWarning, ...],
        processor_name: str,
        processor_version: str,
    ) -> StructuredTranscriptionResult:
        digest = transcription_input.configuration.configuration_digest
        cache_key = build_transcription_cache_key(
            transcription_input,
            processor_name=processor_name,
            processor_version=processor_version,
        )
        status = _result_status(items, omissions, warnings)
        result_id = _result_id(
            transcription_input.input_id,
            items,
            omissions,
            warnings,
            status,
            processor_name,
            processor_version,
            digest,
            cache_key,
        )
        return cls(
            result_id=result_id,
            transcription_input=transcription_input,
            items=items,
            omissions=omissions,
            warnings=warnings,
            status=status,
            processor_name=processor_name,
            processor_version=processor_version,
            configuration_digest=digest,
            cache_key=cache_key,
        )

    def __post_init__(self) -> None:
        if self.contract_version != TRANSCRIPTION_CONTRACT_VERSION:
            raise ValueError("unsupported structured transcription version")
        _validate_result(self)
        expected = _result_id(
            self.transcription_input.input_id,
            self.items,
            self.omissions,
            self.warnings,
            self.status,
            self.processor_name,
            self.processor_version,
            self.configuration_digest,
            self.cache_key,
        )
        if self.result_id != expected:
            raise ValueError(
                "structured transcription result ID is inconsistent"
            )


@dataclass(frozen=True)
class _Draft:
    item_kind: TranscriptionItemKind
    source_object_kind: TranscriptionSourceObjectKind
    source_object_id: str
    page_index: int
    printed_page_label: str | None
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    source_texts: tuple[str, ...]
    evidence_status: TranscriptionEvidenceStatus
    confidence: float | None
    structure_reading_order: int | None
    evidence: Metadata
    warning_codes: tuple[str, ...] = ()

    @property
    def item_id(self) -> str:
        normalized = (
            _normalize_text(self.source_texts) if self.source_texts else None
        )
        method = (
            TRANSCRIPTION_NORMALIZATION_METHOD if self.source_texts else None
        )
        return _item_id(
            self.item_kind,
            self.source_object_kind,
            self.source_object_id,
            self.page_index,
            self.source_block_ids,
            self.source_spans,
            normalized,
            self.source_texts,
            method,
            self.evidence_status,
            self.confidence,
            self.evidence,
        )


class DeterministicStructuredTranscriptionComposer(
    BaseStructuredTranscriptionComposer
):
    """Compose exact evidence into a destination-independent proposal."""

    name = "deterministic-structured-transcription-composer"
    version = TRANSCRIPTION_COMPOSER_VERSION

    def compose(
        self, transcription_input: TranscriptionInput
    ) -> StructuredTranscriptionResult:
        if not isinstance(transcription_input, TranscriptionInput):
            raise TypeError("transcription_input must be TranscriptionInput")
        document = transcription_input.document
        configuration = transcription_input.configuration
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
        drafts: list[_Draft] = []
        omissions: list[TranscriptionOmission] = []
        warnings: list[IngestionWarning] = []
        claimed: dict[str, list[str]] = {}

        for page in document.pages:
            drafts.append(_page_anchor_draft(document, page))

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
            item_kind = _item_kind_for_node(node)
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
                draft = _structure_draft(
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
                    draft = _raw_block_draft(
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

        drafts.sort(key=lambda draft: _draft_order_key(draft, block_position))
        items: list[TranscriptionItem] = []
        for order_index, draft in enumerate(drafts):
            order_status = _draft_order_status(draft)
            item_warnings: list[IngestionWarning] = []
            for code in draft.warning_codes:
                item_warnings.append(_draft_warning(draft, code))
            if order_status is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER:
                item_warnings.append(
                    _draft_warning(draft, "transcription.order_uncertain")
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
            warnings=_deduplicate_warnings(tuple(warnings)),
            processor_name=self.name,
            processor_version=self.version,
        )
        _validate_configured_result(result, configuration)
        return result

    @staticmethod
    def _equation_drafts(
        transcription_input: TranscriptionInput,
    ) -> list[_Draft]:
        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        result: list[_Draft] = []
        for (
            candidate
        ) in transcription_input.equation_detection_result.candidates:
            page_index = candidate.source_spans[0].page_index
            result.append(
                _Draft(
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
                    evidence_status=_equation_status(candidate),
                    confidence=candidate.confidence,
                    structure_reading_order=None,
                    evidence=(("candidate_kind", candidate.kind.value),),
                )
            )
        return result

    @staticmethod
    def _table_drafts(
        transcription_input: TranscriptionInput,
    ) -> list[_Draft]:
        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        structure_result = transcription_input.table_structure_result
        detection = structure_result.structure_input.detection_result
        candidate_by_id = {
            candidate.candidate_id: candidate
            for candidate in detection.candidates
        }
        result: list[_Draft] = []
        for structure in structure_result.structures:
            candidate = candidate_by_id[structure.candidate_id]
            block_ids, spans = _table_projection(structure, candidate)
            page_index = min(region.page_index for region in candidate.regions)
            result.append(
                _Draft(
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
                    evidence_status=_table_status(structure),
                    confidence=structure.confidence,
                    structure_reading_order=None,
                    evidence=(("candidate_id", candidate.candidate_id),),
                )
            )
        return result

    @staticmethod
    def _figure_drafts(
        transcription_input: TranscriptionInput,
    ) -> list[_Draft]:
        document = transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        result: list[_Draft] = []
        for candidate in transcription_input.figure_detection_result.candidates:
            block_ids, spans = _figure_projection(candidate)
            result.append(
                _Draft(
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
                    evidence_status=_figure_status(candidate),
                    confidence=candidate.confidence,
                    structure_reading_order=None,
                    evidence=(
                        ("component_count", str(len(candidate.components))),
                    ),
                )
            )
        return result


def build_transcription_cache_key(
    transcription_input: TranscriptionInput,
    *,
    processor_name: str = "deterministic-structured-transcription-composer",
    processor_version: str = TRANSCRIPTION_COMPOSER_VERSION,
) -> str:
    if not isinstance(transcription_input, TranscriptionInput):
        raise TypeError("transcription_input must be TranscriptionInput")
    _identity_fields(processor_name, processor_version)
    return stable_id(
        "structured-transcription-cache",
        TRANSCRIPTION_CONTRACT_VERSION,
        TRANSCRIPTION_CONFIGURATION_VERSION,
        transcription_input.input_id,
        processor_name,
        processor_version,
        transcription_input.configuration.identity_parts(),
    )


def _validate_input_parts(
    document: ExtractedDocument,
    structure_analysis: StructureAnalysis,
    equation_detection_result: EquationDetectionResult,
    table_structure_result: TableStructureResult,
    figure_detection_result: FigureDetectionResult,
    configuration: TranscriptionConfiguration,
) -> None:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("document must be ExtractedDocument")
    if document.document_id != stable_id("document", document.source.source_id):
        raise ValueError("transcription document identity is stale")
    if not isinstance(structure_analysis, StructureAnalysis):
        raise TypeError("structure_analysis must be StructureAnalysis")
    if structure_analysis.analysis_id is None or (
        structure_analysis.source_id != document.source.source_id
        or structure_analysis.source_blob_id != document.source.blob_id
    ):
        raise ValueError("structure analysis must refer to the exact document")
    if not isinstance(equation_detection_result, EquationDetectionResult):
        raise TypeError("equation result must be EquationDetectionResult")
    if equation_detection_result.detection_input.document != document:
        raise ValueError("equation result must retain the exact document")
    if not isinstance(table_structure_result, TableStructureResult):
        raise TypeError("table result must be TableStructureResult")
    table_detection = table_structure_result.structure_input.detection_result
    table_document = table_detection.detection_input.document
    if table_document != document:
        raise ValueError("table result must retain the exact document")
    if not isinstance(figure_detection_result, FigureDetectionResult):
        raise TypeError("figure result must be FigureDetectionResult")
    if figure_detection_result.detection_input.document != document:
        raise ValueError("figure result must retain the exact document")
    if not isinstance(configuration, TranscriptionConfiguration):
        raise TypeError("configuration must be TranscriptionConfiguration")
    for page in document.pages:
        if not math.isfinite(page.width) or not math.isfinite(page.height):
            raise ValueError("document page dimensions must be finite")
        _unit_float("page extraction quality", page.extraction_quality)
        for block in page.blocks:
            if block.block_id != _expected_block_id(block):
                raise ValueError("document block identity is stale")
            _unit_float("block confidence", block.confidence)
            _validate_exact_source_spans(block.source_spans, document)
            if block.text is not None:
                _bounded_string(
                    "source text",
                    block.text,
                    limit=configuration.max_text_characters_per_item,
                )
    blocks = tuple(block for page in document.pages for block in page.blocks)
    typed_count = (
        len(equation_detection_result.candidates)
        + len(table_detection.candidates)
        + len(table_structure_result.structures)
        + len(figure_detection_result.candidates)
    )
    if len(blocks) > configuration.max_input_blocks:
        raise TranscriptionLimitError("input blocks exceed max_input_blocks")
    if len(structure_analysis.nodes) > configuration.max_input_nodes:
        raise TranscriptionLimitError("input nodes exceed max_input_nodes")
    if typed_count > configuration.max_typed_objects:
        raise TranscriptionLimitError("typed objects exceed max_typed_objects")
    block_ids = {block.block_id for block in blocks}
    if len(block_ids) != len(blocks):
        raise ValueError("document block IDs must be globally unique")
    text_lengths = tuple(
        len(block.text) for block in blocks if block.text is not None
    )
    if any(
        length > configuration.max_text_characters_per_item
        for length in text_lengths
    ):
        raise TranscriptionLimitError(
            "source text exceeds max_text_characters_per_item"
        )
    if sum(text_lengths) > configuration.max_total_text_characters:
        raise TranscriptionLimitError(
            "source text exceeds max_total_text_characters"
        )
    if structure_analysis.input_block_ids != tuple(
        block.block_id for block in blocks
    ):
        raise ValueError("structure analysis input blocks are incomplete")
    for node in structure_analysis.nodes:
        if not set(node.source_block_ids).issubset(block_ids):
            raise ValueError("structure node source blocks are stale")
        _validate_exact_source_spans(node.source_spans, document)
    for equation_candidate in equation_detection_result.candidates:
        if equation_candidate.source_block_id not in block_ids:
            raise ValueError("equation candidate source block is stale")
        _validate_exact_source_spans(equation_candidate.source_spans, document)
    table_candidate_by_id = {
        candidate.candidate_id: candidate
        for candidate in table_detection.candidates
    }
    for structure in table_structure_result.structures:
        table_candidate = table_candidate_by_id.get(structure.candidate_id)
        if table_candidate is None:
            raise ValueError("table structure candidate is stale")
        table_block_ids, table_spans = _table_projection(
            structure, table_candidate
        )
        if not set(table_block_ids).issubset(block_ids):
            raise ValueError("table structure source blocks are stale")
        _validate_exact_source_spans(table_spans, document)
    for figure_candidate in figure_detection_result.candidates:
        candidate_blocks = {
            block_id
            for component in figure_candidate.components
            for block_id in component.source_block_ids
        } | {
            association.block_id
            for association in figure_candidate.associations
        }
        if not candidate_blocks.issubset(block_ids):
            raise ValueError("figure candidate source blocks are stale")
        _validate_exact_source_spans(figure_candidate.source_spans, document)
    artifact_bytes = _input_artifact_bytes(
        equation_detection_result,
        table_structure_result,
        figure_detection_result,
    )
    if artifact_bytes > configuration.max_input_artifact_bytes:
        raise TranscriptionLimitError(
            "input artifacts exceed max_input_artifact_bytes"
        )
    _validate_retained_size(
        (
            document,
            structure_analysis,
            equation_detection_result,
            table_structure_result,
            figure_detection_result,
            configuration,
        ),
        configuration.max_result_bytes,
    )


def _expected_block_id(block: ExtractedBlock) -> str:
    has_source_local_evidence = any(
        span.source_object_id is not None
        or span.bounding_box is not None
        or span.start_offset is not None
        for span in block.source_spans
    )
    fallback_payload = (
        None
        if has_source_local_evidence
        else (block.text, block.asset_id, block.asset_mask_id)
    )
    return stable_id(
        "block",
        block.kind,
        tuple(span.identity_parts() for span in block.source_spans),
        fallback_payload,
    )


def _input_artifact_bytes(
    equation_result: EquationDetectionResult,
    table_result: TableStructureResult,
    figure_result: FigureDetectionResult,
) -> int:
    rendered: dict[str, RenderedRegion] = {}
    embedded: dict[str, EmbeddedFigureArtifact] = {}
    for equation_candidate in equation_result.candidates:
        rendered[equation_candidate.rendered_region.region_id] = (
            equation_candidate.rendered_region
        )
    for (
        table_candidate
    ) in table_result.structure_input.detection_result.candidates:
        for region in table_candidate.regions:
            rendered[region.rendered_region.region_id] = region.rendered_region
    for page in figure_result.detection_input.page_evidence:
        for artifact in page.embedded_artifacts:
            embedded[artifact.artifact_id] = artifact
    for figure_candidate in figure_result.candidates:
        for component in figure_candidate.components:
            if component.rendered_region is not None:
                rendered[component.rendered_region.region_id] = (
                    component.rendered_region
                )
    return sum(region.byte_length for region in rendered.values()) + sum(
        artifact.byte_length + (artifact.mask_byte_length or 0)
        for artifact in embedded.values()
    )


def _document_evidence_id(document: ExtractedDocument) -> str:
    return stable_id("structured-transcription-document-evidence", document)


def _input_id(
    document_evidence_id: str,
    document: ExtractedDocument,
    structure_analysis: StructureAnalysis,
    equation_result: EquationDetectionResult,
    table_result: TableStructureResult,
    figure_result: FigureDetectionResult,
    configuration: TranscriptionConfiguration,
) -> str:
    return stable_id(
        "structured-transcription-input",
        TRANSCRIPTION_CONTRACT_VERSION,
        document_evidence_id,
        document.document_id,
        document.source.source_id,
        document.source.blob_id,
        structure_analysis.analysis_id,
        equation_result.result_id,
        table_result.result_id,
        figure_result.result_id,
        configuration.identity_parts(),
    )


def _page_anchor_draft(
    document: ExtractedDocument, page: ExtractedPage
) -> _Draft:
    object_id = stable_id(
        "transcription-page-anchor",
        document.source.source_id,
        document.source.blob_id,
        page.page_index,
    )
    return _Draft(
        item_kind=TranscriptionItemKind.PAGE_ANCHOR,
        source_object_kind=TranscriptionSourceObjectKind.PAGE,
        source_object_id=object_id,
        page_index=page.page_index,
        printed_page_label=page.printed_page_label,
        source_block_ids=(),
        source_spans=(),
        source_texts=(),
        evidence_status=TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM,
        confidence=None,
        structure_reading_order=None,
        evidence=(("page_index", str(page.page_index)),),
    )


def _structure_draft(
    node: StructureNode,
    blocks: tuple[ExtractedBlock, ...],
    item_kind: TranscriptionItemKind,
    page_label_by_index: dict[int, str | None],
) -> _Draft:
    spans = _deduplicate_spans(
        tuple(span for block in blocks for span in block.source_spans)
    )
    page_index = min(span.page_index for span in spans)
    label = page_label_by_index[page_index]
    return _Draft(
        item_kind=item_kind,
        source_object_kind=TranscriptionSourceObjectKind.STRUCTURE_NODE,
        source_object_id=node.node_id,
        page_index=page_index,
        printed_page_label=label,
        source_block_ids=tuple(block.block_id for block in blocks),
        source_spans=spans,
        source_texts=tuple(
            block.text for block in blocks if block.text is not None
        ),
        evidence_status=_structure_status(node),
        confidence=node.confidence,
        structure_reading_order=node.reading_order,
        evidence=(("structure_kind", node.kind.value),),
    )


def _raw_block_draft(
    page_index: int,
    printed_page_label: str | None,
    block: ExtractedBlock,
) -> _Draft:
    assert block.text is not None
    return _Draft(
        item_kind=TranscriptionItemKind.PROSE,
        source_object_kind=TranscriptionSourceObjectKind.RAW_BLOCK,
        source_object_id=block.block_id,
        page_index=page_index,
        printed_page_label=printed_page_label,
        source_block_ids=(block.block_id,),
        source_spans=block.source_spans,
        source_texts=(block.text,),
        evidence_status=TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM,
        confidence=block.confidence,
        structure_reading_order=None,
        evidence=(("fallback", "raw_block"),),
        warning_codes=("transcription.raw_block_fallback",),
    )


def _item_kind_for_node(node: StructureNode) -> TranscriptionItemKind | None:
    if node.kind in (
        StructureKind.TITLE,
        StructureKind.PART,
        StructureKind.CHAPTER,
        StructureKind.SECTION,
        StructureKind.SUBSECTION,
        StructureKind.APPENDIX,
    ):
        return TranscriptionItemKind.HEADING
    if node.kind is StructureKind.EQUATION:
        return TranscriptionItemKind.EQUATION
    if node.kind is StructureKind.TABLE:
        return TranscriptionItemKind.TABLE
    if node.kind is StructureKind.FIGURE:
        return TranscriptionItemKind.FIGURE
    if node.kind in (
        StructureKind.DOCUMENT,
        StructureKind.FRONT_MATTER,
        StructureKind.PROBLEM_SET,
        StructureKind.BIBLIOGRAPHY,
        StructureKind.INDEX,
    ):
        return None
    return TranscriptionItemKind.PROSE


def _draft_order_key(
    draft: _Draft,
    block_position: dict[str, tuple[int, int]],
) -> tuple[object, ...]:
    if draft.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
        return (draft.page_index, 0, 0.0, 0.0, 0, draft.source_object_id)
    boxes = tuple(
        span.bounding_box
        for span in draft.source_spans
        if span.page_index == draft.page_index and span.bounding_box is not None
    )
    if boxes:
        y = min(box[1] for box in boxes)
        x = min(box[0] for box in boxes)
        fallback = 0
    elif draft.structure_reading_order is not None:
        y = float(draft.structure_reading_order)
        x = 0.0
        fallback = 1
    else:
        positions = tuple(
            block_position[block_id][1]
            for block_id in draft.source_block_ids
            if block_id in block_position
        )
        y = float(min(positions)) if positions else math.inf
        x = 0.0
        fallback = 2
    priority = {
        TranscriptionItemKind.HEADING: 0,
        TranscriptionItemKind.PROSE: 1,
        TranscriptionItemKind.EQUATION: 2,
        TranscriptionItemKind.TABLE: 3,
        TranscriptionItemKind.FIGURE: 4,
        TranscriptionItemKind.PAGE_ANCHOR: 0,
    }[draft.item_kind]
    return (
        draft.page_index,
        1,
        fallback,
        y,
        x,
        priority,
        draft.source_object_id,
    )


def _draft_order_status(draft: _Draft) -> TranscriptionOrderStatus:
    if draft.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
        return TranscriptionOrderStatus.PAGE_ANCHOR
    if any(
        span.page_index == draft.page_index and span.bounding_box is not None
        for span in draft.source_spans
    ):
        return TranscriptionOrderStatus.PROPOSED_GEOMETRIC
    if draft.structure_reading_order is not None:
        return TranscriptionOrderStatus.PROPOSED_STRUCTURE
    return TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER


def _draft_warning(draft: _Draft, code: str) -> IngestionWarning:
    if code == "transcription.order_uncertain":
        message = (
            "Item ordering uses uncertain extractor source order because "
            "geometry and structure order are unavailable."
        )
    else:
        message = (
            "Raw text is included as an explicit fallback because no selected "
            "structure item represents the block."
        )
    return IngestionWarning.create(
        code=code,
        severity=WarningSeverity.WARNING,
        message=message,
        object_ids=(draft.source_object_id,),
        source_spans=draft.source_spans,
        evidence=(("item_kind", draft.item_kind.value),),
    )


def _table_projection(
    structure: TableStructure,
    candidate: TableCandidate,
) -> tuple[tuple[str, ...], tuple[SourceSpan, ...]]:
    block_ids = _deduplicate_strings(
        tuple(
            block_id
            for region in candidate.regions
            for block_id in region.block_ids
        )
        + tuple(association.block_id for association in candidate.associations)
        + tuple(
            block_id
            for cell in structure.cells
            for block_id in cell.source_block_ids
        )
    )
    spans = _deduplicate_spans(
        candidate.source_spans
        + tuple(span for row in structure.rows for span in row.source_spans)
        + tuple(span for cell in structure.cells for span in cell.source_spans)
    )
    return block_ids, spans


def _figure_projection(
    candidate: FigureCandidate,
) -> tuple[tuple[str, ...], tuple[SourceSpan, ...]]:
    block_ids = _deduplicate_strings(
        tuple(
            block_id
            for component in candidate.components
            for block_id in component.source_block_ids
        )
        + tuple(association.block_id for association in candidate.associations)
    )
    return block_ids, candidate.source_spans


def _equation_status(
    candidate: EquationCandidate,
) -> TranscriptionEvidenceStatus:
    if candidate.evidence_status is EquationEvidenceStatus.AMBIGUOUS:
        return TranscriptionEvidenceStatus.AMBIGUOUS
    return TranscriptionEvidenceStatus.PROPOSED


def _table_status(structure: TableStructure) -> TranscriptionEvidenceStatus:
    if structure.evidence_status is TableStructureEvidenceStatus.AMBIGUOUS:
        return TranscriptionEvidenceStatus.AMBIGUOUS
    return TranscriptionEvidenceStatus.PROPOSED


def _figure_status(candidate: FigureCandidate) -> TranscriptionEvidenceStatus:
    if candidate.evidence_status is FigureEvidenceStatus.AMBIGUOUS:
        return TranscriptionEvidenceStatus.AMBIGUOUS
    return TranscriptionEvidenceStatus.PROPOSED


def _structure_status(node: StructureNode) -> TranscriptionEvidenceStatus:
    if node.evidence_status is StructureEvidenceStatus.UNCERTAIN:
        return TranscriptionEvidenceStatus.AMBIGUOUS
    return TranscriptionEvidenceStatus.PROPOSED


def _normalize_text(source_texts: tuple[str, ...]) -> str:
    return _WHITESPACE.sub(" ", "\n".join(source_texts)).strip()


def _item_id(
    item_kind: TranscriptionItemKind,
    source_object_kind: TranscriptionSourceObjectKind,
    source_object_id: str,
    page_index: int,
    source_block_ids: tuple[str, ...],
    source_spans: tuple[SourceSpan, ...],
    normalized_text: str | None,
    source_texts: tuple[str, ...],
    normalization_method: str | None,
    evidence_status: TranscriptionEvidenceStatus,
    confidence: float | None,
    evidence: Metadata,
) -> str:
    return stable_id(
        "structured-transcription-item",
        item_kind.value,
        source_object_kind.value,
        source_object_id,
        page_index,
        source_block_ids,
        tuple(_span_parts(span) for span in source_spans),
        normalized_text,
        source_texts,
        normalization_method,
        evidence_status.value,
        confidence,
        evidence,
    )


def _omission_id(
    omitted_object_id: str,
    source_block_id: str,
    source_spans: tuple[SourceSpan, ...],
    reason: TranscriptionOmissionReason,
    represented_by_item_ids: tuple[str, ...],
    evidence: Metadata,
) -> str:
    return stable_id(
        "structured-transcription-omission",
        omitted_object_id,
        source_block_id,
        tuple(_span_parts(span) for span in source_spans),
        reason.value,
        represented_by_item_ids,
        evidence,
    )


def _result_status(
    items: tuple[TranscriptionItem, ...],
    omissions: tuple[TranscriptionOmission, ...],
    warnings: tuple[IngestionWarning, ...],
) -> TranscriptionStatus:
    if (
        omissions
        or warnings
        or any(
            item.evidence_status is TranscriptionEvidenceStatus.AMBIGUOUS
            or item.order_status
            is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER
            for item in items
        )
    ):
        return TranscriptionStatus.PROPOSED_WITH_UNCERTAINTY
    return TranscriptionStatus.PROPOSED


def _result_id(
    input_id: str,
    items: tuple[TranscriptionItem, ...],
    omissions: tuple[TranscriptionOmission, ...],
    warnings: tuple[IngestionWarning, ...],
    status: TranscriptionStatus,
    processor_name: str,
    processor_version: str,
    configuration_digest: str,
    cache_key: str,
) -> str:
    return stable_id(
        "structured-transcription-result",
        input_id,
        tuple(
            (
                item.item_id,
                item.order_index,
                item.order_status.value,
                item.warning_ids,
            )
            for item in items
        ),
        tuple(item.omission_id for item in omissions),
        tuple(warning.warning_id for warning in warnings),
        status.value,
        processor_name,
        processor_version,
        configuration_digest,
        cache_key,
    )


def _validate_result(result: StructuredTranscriptionResult) -> None:
    if not isinstance(result.transcription_input, TranscriptionInput):
        raise TypeError("transcription result input is unsupported")
    _require_tuple("transcription items", result.items)
    _require_tuple("transcription omissions", result.omissions)
    _require_tuple("transcription warnings", result.warnings)
    if any(not isinstance(item, TranscriptionItem) for item in result.items):
        raise TypeError("transcription items contain an unsupported value")
    if any(
        not isinstance(item, TranscriptionOmission) for item in result.omissions
    ):
        raise TypeError("transcription omissions contain an unsupported value")
    if any(not isinstance(item, IngestionWarning) for item in result.warnings):
        raise TypeError("transcription warnings contain an unsupported value")
    _identity_fields(result.processor_name, result.processor_version)
    configuration = result.transcription_input.configuration
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("transcription configuration digest is inconsistent")
    expected_cache = build_transcription_cache_key(
        result.transcription_input,
        processor_name=result.processor_name,
        processor_version=result.processor_version,
    )
    if result.cache_key != expected_cache:
        raise ValueError("transcription cache key is inconsistent")
    if tuple(item.order_index for item in result.items) != tuple(
        range(len(result.items))
    ):
        raise ValueError("transcription item order indices are inconsistent")
    item_ids = tuple(item.item_id for item in result.items)
    omission_ids = tuple(item.omission_id for item in result.omissions)
    warning_ids = tuple(item.warning_id for item in result.warnings)
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("transcription item IDs must be unique")
    source_object_keys = tuple(
        (item.source_object_kind, item.source_object_id)
        for item in result.items
    )
    if len(set(source_object_keys)) != len(source_object_keys):
        raise ValueError("transcription source objects must be unique")
    if len(set(omission_ids)) != len(omission_ids):
        raise ValueError("transcription omission IDs must be unique")
    omission_source_keys = tuple(
        (item.omitted_object_id, item.source_block_id)
        for item in result.omissions
    )
    if len(set(omission_source_keys)) != len(omission_source_keys):
        raise ValueError("transcription omission sources must be unique")
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("transcription warning IDs must be unique")
    if any(
        not set(item.warning_ids).issubset(warning_ids) for item in result.items
    ):
        raise ValueError("transcription item warning link is unresolved")
    if any(
        not set(item.warning_ids).issubset(warning_ids)
        for item in result.omissions
    ):
        raise ValueError("transcription omission warning link is unresolved")
    if any(
        not set(item.represented_by_item_ids).issubset(item_ids)
        for item in result.omissions
    ):
        raise ValueError("transcription omission item link is unresolved")
    valid_warning_object_ids = (
        set(item_ids)
        | {item.source_object_id for item in result.items}
        | set(omission_ids)
        | {item.source_block_id for item in result.omissions}
    )
    for warning in result.warnings:
        _validate_composition_warning(
            warning,
            result.transcription_input.document,
            valid_warning_object_ids,
        )
    _validate_result_objects(result)
    if result.status is not _result_status(
        result.items, result.omissions, result.warnings
    ):
        raise ValueError("transcription status is inconsistent")
    _validate_configured_result(result, configuration)


def _validate_composition_warning(
    warning: IngestionWarning,
    document: ExtractedDocument,
    valid_object_ids: set[str],
) -> None:
    _bounded_string("warning code", warning.code, nonempty=True)
    _bounded_string(
        "warning message",
        warning.message,
        nonempty=True,
        limit=_MAX_TEXT_CHARACTERS_PER_ITEM,
    )
    if not isinstance(warning.severity, WarningSeverity):
        raise TypeError("transcription warning severity is unsupported")
    _unique_strings("warning object IDs", warning.object_ids)
    if not set(warning.object_ids).issubset(valid_object_ids):
        raise ValueError("transcription warning object link is unresolved")
    _validate_exact_source_spans(warning.source_spans, document)
    _validate_metadata(warning.evidence)
    if warning.suggested_recovery is not None:
        _bounded_string(
            "warning suggested recovery",
            warning.suggested_recovery,
            nonempty=True,
            limit=_MAX_TEXT_CHARACTERS_PER_ITEM,
        )
    expected = stable_id(
        "warning",
        warning.code,
        warning.object_ids,
        tuple(span.identity_parts() for span in warning.source_spans),
        warning.evidence,
    )
    if warning.warning_id != expected:
        raise ValueError("transcription warning ID is inconsistent")


def _validate_result_objects(result: StructuredTranscriptionResult) -> None:
    transcription_input = result.transcription_input
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
    equation_candidates = (
        transcription_input.equation_detection_result.candidates
    )
    equation_by_id = {
        candidate.candidate_id: candidate for candidate in equation_candidates
    }
    table_result = transcription_input.table_structure_result
    table_by_id = {
        structure.structure_id: structure
        for structure in table_result.structures
    }
    table_candidates = table_result.structure_input.detection_result.candidates
    table_candidate_by_id = {
        candidate.candidate_id: candidate for candidate in table_candidates
    }
    figure_by_id = {
        candidate.candidate_id: candidate
        for candidate in transcription_input.figure_detection_result.candidates
    }
    warning_by_id = {warning.warning_id: warning for warning in result.warnings}
    page_by_anchor_id = {
        stable_id(
            "transcription-page-anchor",
            document.source.source_id,
            document.source.blob_id,
            page.page_index,
        ): page
        for page in document.pages
    }
    for item in result.items:
        page = page_by_index.get(item.page_index)
        if page is None:
            raise ValueError("transcription item page is unresolved")
        if item.printed_page_label != page.printed_page_label:
            raise ValueError("transcription item printed page label is stale")
        if not set(item.source_block_ids).issubset(block_by_id):
            raise ValueError("transcription item source block is unresolved")
        _validate_exact_source_spans(item.source_spans, document)
        if item.source_object_kind is TranscriptionSourceObjectKind.PAGE:
            source_page = page_by_anchor_id.get(item.source_object_id)
            if source_page is None or source_page.page_index != item.page_index:
                raise ValueError("transcription page anchor is unresolved")
            if (
                item.item_kind is not TranscriptionItemKind.PAGE_ANCHOR
                or item.source_block_ids
                or item.source_spans
                or item.source_texts
                or item.confidence is not None
                or item.order_status is not TranscriptionOrderStatus.PAGE_ANCHOR
                or item.evidence_status
                is not TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM
            ):
                raise ValueError("transcription page anchor is inconsistent")
        elif item.source_object_kind is TranscriptionSourceObjectKind.RAW_BLOCK:
            block = block_by_id.get(item.source_object_id)
            if block is None or block.text is None:
                raise ValueError("transcription raw block is unresolved")
            _validate_item_projection(
                item,
                expected_kind=TranscriptionItemKind.PROSE,
                expected_block_ids=(block.block_id,),
                expected_spans=block.source_spans,
                expected_texts=(block.text,),
                expected_confidence=block.confidence,
                expected_status=(
                    TranscriptionEvidenceStatus.OBSERVED_SOURCE_TRANSFORM
                ),
            )
            if "transcription.raw_block_fallback" not in {
                warning_by_id[warning_id].code
                for warning_id in item.warning_ids
            }:
                raise ValueError("raw-block fallback lacks a warning")
        elif (
            item.source_object_kind
            is TranscriptionSourceObjectKind.STRUCTURE_NODE
        ):
            node = node_by_id.get(item.source_object_id)
            expected_kind = (
                _item_kind_for_node(node) if node is not None else None
            )
            if (
                node is None
                or expected_kind is None
                or not set(item.source_block_ids).issubset(
                    node.source_block_ids
                )
            ):
                raise ValueError("transcription structure node is unresolved")
            blocks = tuple(
                block_by_id[value] for value in item.source_block_ids
            )
            _validate_item_projection(
                item,
                expected_kind=expected_kind,
                expected_block_ids=item.source_block_ids,
                expected_spans=_deduplicate_spans(
                    tuple(
                        span for block in blocks for span in block.source_spans
                    )
                ),
                expected_texts=tuple(
                    block.text for block in blocks if block.text is not None
                ),
                expected_confidence=node.confidence,
                expected_status=_structure_status(node),
            )
        elif (
            item.source_object_kind
            is TranscriptionSourceObjectKind.EQUATION_CANDIDATE
        ):
            equation_candidate = equation_by_id.get(item.source_object_id)
            if equation_candidate is None:
                raise ValueError(
                    "transcription equation candidate is unresolved"
                )
            _validate_item_projection(
                item,
                expected_kind=TranscriptionItemKind.EQUATION,
                expected_block_ids=(equation_candidate.source_block_id,),
                expected_spans=equation_candidate.source_spans,
                expected_texts=(equation_candidate.raw_text,),
                expected_confidence=equation_candidate.confidence,
                expected_status=_equation_status(equation_candidate),
            )
        elif (
            item.source_object_kind
            is TranscriptionSourceObjectKind.TABLE_STRUCTURE
        ):
            structure = table_by_id.get(item.source_object_id)
            if structure is None:
                raise ValueError("transcription table structure is unresolved")
            table_candidate = table_candidate_by_id[structure.candidate_id]
            block_ids, spans = _table_projection(structure, table_candidate)
            _validate_item_projection(
                item,
                expected_kind=TranscriptionItemKind.TABLE,
                expected_block_ids=block_ids,
                expected_spans=spans,
                expected_texts=(),
                expected_confidence=structure.confidence,
                expected_status=_table_status(structure),
            )
        else:
            figure_candidate = figure_by_id.get(item.source_object_id)
            if figure_candidate is None:
                raise ValueError("transcription figure candidate is unresolved")
            block_ids, spans = _figure_projection(figure_candidate)
            _validate_item_projection(
                item,
                expected_kind=TranscriptionItemKind.FIGURE,
                expected_block_ids=block_ids,
                expected_spans=spans,
                expected_texts=(),
                expected_confidence=figure_candidate.confidence,
                expected_status=_figure_status(figure_candidate),
            )
        structure_node = (
            node_by_id.get(item.source_object_id)
            if item.source_object_kind
            is TranscriptionSourceObjectKind.STRUCTURE_NODE
            else None
        )
        _validate_item_order_evidence(item, structure_node, warning_by_id)
    page_anchor_indices = tuple(
        item.page_index
        for item in result.items
        if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR
    )
    if page_anchor_indices != tuple(page_by_index):
        raise ValueError("transcription page anchors are incomplete")
    for source_kind, expected_ids in (
        (
            TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
            set(equation_by_id),
        ),
        (TranscriptionSourceObjectKind.TABLE_STRUCTURE, set(table_by_id)),
        (TranscriptionSourceObjectKind.FIGURE_CANDIDATE, set(figure_by_id)),
    ):
        actual_ids = {
            item.source_object_id
            for item in result.items
            if item.source_object_kind is source_kind
        }
        if actual_ids != expected_ids:
            raise ValueError(
                "transcription typed-object coverage is incomplete"
            )
    item_by_id = {item.item_id: item for item in result.items}
    typed_source_kinds = {
        TranscriptionSourceObjectKind.EQUATION_CANDIDATE,
        TranscriptionSourceObjectKind.TABLE_STRUCTURE,
        TranscriptionSourceObjectKind.FIGURE_CANDIDATE,
    }
    for omission in result.omissions:
        block = block_by_id.get(omission.source_block_id)
        if block is None or omission.source_spans != block.source_spans:
            raise ValueError(
                "transcription omission source block is unresolved"
            )
        if omission.omitted_object_id != block.block_id:
            node = node_by_id.get(omission.omitted_object_id)
            if node is None or block.block_id not in node.source_block_ids:
                raise ValueError("transcription omitted object is unresolved")
        linked_items = tuple(
            item_by_id[item_id] for item_id in omission.represented_by_item_ids
        )
        if any(
            block.block_id not in item.source_block_ids for item in linked_items
        ):
            raise ValueError(
                "transcription omission replacement does not cover its block"
            )
        if omission.reason is (
            TranscriptionOmissionReason.REPRESENTED_BY_TYPED_OBJECT
        ) and not any(
            item.source_object_kind in typed_source_kinds
            for item in linked_items
        ):
            raise ValueError("typed-object omission lacks a typed replacement")
        if omission.reason is (
            TranscriptionOmissionReason.REPRESENTED_BY_EARLIER_ITEM
        ) and any(
            item.source_object_kind in typed_source_kinds
            for item in linked_items
        ):
            raise ValueError("earlier-item omission has a typed replacement")
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
            is (TranscriptionOmissionReason.UNREPRESENTED_NON_TEXT_BLOCK)
            and omission.omitted_object_id != block.block_id
        ):
            raise ValueError("unrepresented omission must identify its block")
    represented_node_ids = {
        item.source_object_id
        for item in result.items
        if item.source_object_kind
        is TranscriptionSourceObjectKind.STRUCTURE_NODE
    } | {item.omitted_object_id for item in result.omissions}
    expected_node_ids = {
        node.node_id
        for node in transcription_input.structure_analysis.nodes
        if _item_kind_for_node(node) is not None and node.source_block_ids
    }
    if not expected_node_ids.issubset(represented_node_ids):
        raise ValueError("transcription structure-node coverage is incomplete")
    represented_blocks = {
        block_id for item in result.items for block_id in item.source_block_ids
    } | {item.source_block_id for item in result.omissions}
    if represented_blocks != set(block_by_id):
        raise ValueError("transcription raw block coverage is incomplete")


def _validate_item_order_evidence(
    item: TranscriptionItem,
    structure_node: StructureNode | None,
    warning_by_id: dict[str, IngestionWarning],
) -> None:
    if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
        expected = TranscriptionOrderStatus.PAGE_ANCHOR
    elif any(
        span.page_index == item.page_index and span.bounding_box is not None
        for span in item.source_spans
    ):
        expected = TranscriptionOrderStatus.PROPOSED_GEOMETRIC
    elif (
        structure_node is not None and structure_node.reading_order is not None
    ):
        expected = TranscriptionOrderStatus.PROPOSED_STRUCTURE
    else:
        expected = TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER
    if item.order_status is not expected:
        raise ValueError("transcription item order evidence is inconsistent")
    warning_codes = {
        warning_by_id[warning_id].code for warning_id in item.warning_ids
    }
    if expected is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER and (
        "transcription.order_uncertain" not in warning_codes
    ):
        raise ValueError("uncertain transcription order lacks a warning")


def _validate_item_projection(
    item: TranscriptionItem,
    *,
    expected_kind: TranscriptionItemKind,
    expected_block_ids: tuple[str, ...],
    expected_spans: tuple[SourceSpan, ...],
    expected_texts: tuple[str, ...],
    expected_confidence: float,
    expected_status: TranscriptionEvidenceStatus,
) -> None:
    if (
        item.item_kind is not expected_kind
        or item.source_block_ids != expected_block_ids
        or item.source_spans != expected_spans
        or item.source_texts != expected_texts
        or item.confidence != expected_confidence
        or item.evidence_status is not expected_status
    ):
        raise ValueError("transcription item projection is inconsistent")


def _validate_configured_result(
    result: StructuredTranscriptionResult,
    configuration: TranscriptionConfiguration,
) -> None:
    if len(result.items) > configuration.max_items:
        raise TranscriptionLimitError("items exceed max_items")
    if len(result.omissions) > configuration.max_omissions:
        raise TranscriptionLimitError("omissions exceed max_omissions")
    if len(result.warnings) > configuration.max_warnings:
        raise TranscriptionLimitError("warnings exceed max_warnings")
    total_spans = sum(len(item.source_spans) for item in result.items) + sum(
        len(item.source_spans) for item in result.omissions
    )
    if total_spans > configuration.max_source_spans:
        raise TranscriptionLimitError("source spans exceed max_source_spans")
    text_lengths = tuple(
        len(item.normalized_text or "")
        + sum(len(text) for text in item.source_texts)
        for item in result.items
    )
    if any(
        length > configuration.max_text_characters_per_item
        for length in text_lengths
    ):
        raise TranscriptionLimitError(
            "item text exceeds max_text_characters_per_item"
        )
    if sum(text_lengths) > configuration.max_total_text_characters:
        raise TranscriptionLimitError("text exceeds max_total_text_characters")
    _validate_retained_size(result, configuration.max_result_bytes)


def _validate_exact_source_spans(
    spans: tuple[SourceSpan, ...], document: ExtractedDocument
) -> None:
    _validate_spans(spans)
    page_by_index = {page.page_index: page for page in document.pages}
    for span in spans:
        if span.source_id != document.source.source_id or (
            span.source_blob_id != document.source.blob_id
        ):
            raise ValueError("transcription span refers to another source")
        page = page_by_index.get(span.page_index)
        if page is None:
            raise ValueError("transcription span page is unresolved")
        if span.printed_page_label is not None and (
            span.printed_page_label != page.printed_page_label
        ):
            raise ValueError("transcription span printed page label is stale")
        if span.bounding_box is not None:
            x0, y0, x1, y1 = span.bounding_box
            if any(not math.isfinite(value) for value in span.bounding_box):
                raise ValueError("transcription span geometry must be finite")
            if x0 < 0 or y0 < 0 or x1 > page.width or y1 > page.height:
                raise ValueError("transcription span exceeds its source page")


def _deduplicate_warnings(
    warnings: tuple[IngestionWarning, ...],
) -> tuple[IngestionWarning, ...]:
    result: list[IngestionWarning] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning.warning_id not in seen:
            seen.add(warning.warning_id)
            result.append(warning)
    return tuple(result)


def _deduplicate_spans(spans: tuple[SourceSpan, ...]) -> tuple[SourceSpan, ...]:
    result: list[SourceSpan] = []
    seen: set[tuple[object, ...]] = set()
    for span in spans:
        identity = _span_parts(span)
        if identity not in seen:
            seen.add(identity)
            result.append(span)
    return tuple(result)


def _deduplicate_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _span_parts(span: SourceSpan) -> tuple[object, ...]:
    return span.identity_parts() + (span.printed_page_label,)


def _validate_spans(spans: tuple[SourceSpan, ...]) -> None:
    _require_tuple("source spans", spans)
    if any(not isinstance(span, SourceSpan) for span in spans):
        raise TypeError("source spans contain an unsupported value")
    identities = tuple(_span_parts(span) for span in spans)
    if len(set(identities)) != len(identities):
        raise ValueError("source spans must be unique")


def _validate_metadata(value: Metadata) -> None:
    _require_tuple("metadata", value)
    if len(value) > _MAX_EVIDENCE_ENTRIES:
        raise TranscriptionLimitError("too many metadata entries")
    total = 0
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise TypeError("metadata must contain immutable pairs")
        key, item = entry
        _bounded_string("metadata key", key, nonempty=True)
        _bounded_string("metadata value", item)
        total += len(key) + len(item)
    if total > _MAX_EVIDENCE_CHARACTERS:
        raise TranscriptionLimitError("metadata exceeds its hard limit")


def _identity_fields(*values: str) -> None:
    for value in values:
        _bounded_string("identity field", value, nonempty=True)


def _unique_strings(name: str, values: tuple[str, ...]) -> None:
    _require_tuple(name, values)
    for value in values:
        _bounded_string(name, value, nonempty=True)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must be unique")


def _require_tuple(name: str, value: object) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be an immutable tuple")


def _bounded_string(
    name: str,
    value: object,
    *,
    nonempty: bool = False,
    limit: int = _MAX_IDENTITY_CHARACTERS,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if nonempty and not value:
        raise ValueError(f"{name} must be non-empty")
    if len(value) > limit:
        raise TranscriptionLimitError(f"{name} exceeds its hard limit")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be valid UTF-8") from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _unit_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite and within [0, 1]")
    return 0.0 if result == 0.0 else result


def _validate_retained_size(value: object, limit: int) -> None:
    total = 0
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if item is None or isinstance(item, (bool, int, float, Enum)):
            total += 16
        elif isinstance(item, str):
            total += len(item.encode("utf-8")) + 8
        elif isinstance(item, bytes):
            total += len(item)
        elif isinstance(item, tuple):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            total += 8 * len(item)
            stack.extend(item)
        elif is_dataclass(item) and not isinstance(item, type):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            for field in fields(item):
                total += len(field.name) + 3
                if field.name in ("content", "mask_content") and (
                    item.__class__.__name__
                    in ("RenderedRegion", "EmbeddedFigureArtifact")
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError("transcription contains unsupported evidence")
        if total > limit:
            raise TranscriptionLimitError(
                "transcription result exceeds max_result_bytes"
            )
