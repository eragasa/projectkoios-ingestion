from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import IngestionWarning
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.derivation.equation import (
    EquationTranscriptionDerivation,
)
from projectkoios.ingestion.transcription.derivation.figure import (
    FigureTranscriptionDerivation,
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
from projectkoios.ingestion.transcription.item.item import TranscriptionItem
from projectkoios.ingestion.transcription.item.projection_validation import (
    TranscriptionItemProjectionValidation,
)
from projectkoios.ingestion.transcription.order.validation import (
    TranscriptionOrderValidation,
)
from projectkoios.ingestion.transcription.request.request import (
    StructuredTranscriptionRequest,
)
from projectkoios.ingestion.transcription.source.object_kind import (
    TranscriptionSourceObjectKind,
)


@dataclass(frozen=True)
class TranscriptionItemSourceValidation(
    AbstractValidation, AbstractTranscriptionDataObject
):
    transcription_input: StructuredTranscriptionRequest
    item: TranscriptionItem
    warnings: tuple[IngestionWarning, ...]
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported item-source validation version")
        document = self.transcription_input.document
        page_by_index = {page.page_index: page for page in document.pages}
        block_by_id = {
            block.block_id: block
            for page in document.pages
            for block in page.blocks
        }
        page = page_by_index.get(self.item.page_index)
        if page is None:
            raise ValueError("transcription item page is unresolved")
        if self.item.printed_page_label != page.printed_page_label:
            raise ValueError("transcription item printed page label is stale")
        if not set(self.item.source_block_ids).issubset(block_by_id):
            raise ValueError("transcription item source block is unresolved")
        self.validate_exact_source_spans(self.item.source_spans, document)
        structure_node = None
        if self.item.source_object_kind is TranscriptionSourceObjectKind.PAGE:
            source_page = next(
                (
                    value
                    for value in document.pages
                    if stable_id(
                        "transcription-page-anchor",
                        document.source.source_id,
                        document.source.blob_id,
                        value.page_index,
                    )
                    == self.item.source_object_id
                ),
                None,
            )
            if source_page is None:
                raise ValueError("transcription page anchor is unresolved")
            TranscriptionItemProjectionValidation(
                self.item,
                PageTranscriptionDerivation.derive(document, source_page),
            )
        elif (
            self.item.source_object_kind
            is TranscriptionSourceObjectKind.RAW_BLOCK
        ):
            block = block_by_id.get(self.item.source_object_id)
            if block is None or block.text is None:
                raise ValueError("transcription raw block is unresolved")
            TranscriptionItemProjectionValidation(
                self.item,
                RawBlockTranscriptionDerivation.derive(
                    self.item.page_index,
                    self.item.printed_page_label,
                    block,
                ),
            )
            if "transcription.raw_block_fallback" not in {
                warning.code for warning in self.warnings
            }:
                raise ValueError("raw-block fallback lacks a warning")
        elif (
            self.item.source_object_kind
            is TranscriptionSourceObjectKind.STRUCTURE_NODE
        ):
            structure_node = next(
                (
                    node
                    for node in (
                        self.transcription_input.structure_analysis.nodes
                    )
                    if node.node_id == self.item.source_object_id
                ),
                None,
            )
            disposition = (
                TranscriptionStructureDisposition.derive(structure_node)
                if structure_node is not None
                else None
            )
            if (
                structure_node is None
                or disposition is None
                or disposition.item_kind is None
                or not set(self.item.source_block_ids).issubset(
                    structure_node.source_block_ids
                )
            ):
                raise ValueError("transcription structure node is unresolved")
            blocks = tuple(
                block_by_id[value] for value in self.item.source_block_ids
            )
            TranscriptionItemProjectionValidation(
                self.item,
                StructureTranscriptionDerivation.derive(
                    structure_node,
                    blocks,
                    {
                        value.page_index: value.printed_page_label
                        for value in document.pages
                    },
                ),
            )
        elif (
            self.item.source_object_kind
            is TranscriptionSourceObjectKind.EQUATION_CANDIDATE
        ):
            equation_candidate = next(
                (
                    value
                    for value in (
                        self.transcription_input.equation_detection_result.candidates
                    )
                    if value.candidate_id == self.item.source_object_id
                ),
                None,
            )
            if equation_candidate is None:
                raise ValueError(
                    "transcription equation candidate is unresolved"
                )
            TranscriptionItemProjectionValidation(
                self.item,
                EquationTranscriptionDerivation.derive(
                    equation_candidate, page.printed_page_label
                ),
            )
        elif (
            self.item.source_object_kind
            is TranscriptionSourceObjectKind.TABLE_STRUCTURE
        ):
            structure = next(
                (
                    value
                    for value in (
                        self.transcription_input.table_structure_result.structures
                    )
                    if value.structure_id == self.item.source_object_id
                ),
                None,
            )
            if structure is None:
                raise ValueError("transcription table structure is unresolved")
            table_candidate = next(
                value
                for value in (
                    self.transcription_input.table_structure_result.structure_input.detection_result.candidates
                )
                if value.candidate_id == structure.candidate_id
            )
            TranscriptionItemProjectionValidation(
                self.item,
                TableTranscriptionDerivation.derive(
                    structure, table_candidate, page.printed_page_label
                ),
            )
        elif (
            self.item.source_object_kind
            is TranscriptionSourceObjectKind.FIGURE_CANDIDATE
        ):
            figure_candidate = next(
                (
                    value
                    for value in (
                        self.transcription_input.figure_detection_result.candidates
                    )
                    if value.candidate_id == self.item.source_object_id
                ),
                None,
            )
            if figure_candidate is None:
                raise ValueError("transcription figure candidate is unresolved")
            TranscriptionItemProjectionValidation(
                self.item,
                FigureTranscriptionDerivation.derive(
                    figure_candidate, page.printed_page_label
                ),
            )
        else:
            raise ValueError("unsupported transcription source-object kind")
        TranscriptionOrderValidation(self.item, structure_node, self.warnings)
