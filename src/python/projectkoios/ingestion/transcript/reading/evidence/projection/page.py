"""Pure page and block assembly for canonical reading projection."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.transcript.reading.evidence.block.equation.projection import (  # noqa: E501
    project_reading_equation_evidence_block,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.projection import (  # noqa: E501
    project_reading_figure_evidence_block,
)
from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlock,
    ReadingEvidenceBlockInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.projection import (  # noqa: E501
    project_reading_table_evidence_block,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.projection import (  # noqa: E501
    project_reading_text_evidence_block,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)
from projectkoios.ingestion.transcript.reading.evidence.page.inventory import (
    ReadingEvidencePageInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.request import (  # noqa: E501
    ReadingEvidenceProjectionRequest,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidencePageProjection:
    """Bind canonical pages to exact producer identities consumed by them."""

    pages: ReadingEvidencePageInventory
    clean_text_ids: ReadingEvidenceIdentityInventory
    figure_ids: ReadingEvidenceIdentityInventory
    table_ids: ReadingEvidenceIdentityInventory
    equation_ids: ReadingEvidenceIdentityInventory

    def __post_init__(self) -> None:
        if type(self.pages) is not ReadingEvidencePageInventory:
            raise TypeError("pages must be ReadingEvidencePageInventory")
        values = (
            (
                self.clean_text_ids,
                ReadingEvidenceIdentityKind.CLEAN_TEXT,
                "clean_text_ids",
            ),
            (
                self.figure_ids,
                ReadingEvidenceIdentityKind.FIGURE,
                "figure_ids",
            ),
            (
                self.table_ids,
                ReadingEvidenceIdentityKind.TABLE,
                "table_ids",
            ),
            (
                self.equation_ids,
                ReadingEvidenceIdentityKind.EQUATION,
                "equation_ids",
            ),
        )
        for inventory, kind, name in values:
            if (
                type(inventory) is not ReadingEvidenceIdentityInventory
                or inventory.kind is not kind
            ):
                raise TypeError(f"{name} has the wrong identity role")


def project_reading_evidence_pages(
    *, request: ReadingEvidenceProjectionRequest
) -> ReadingEvidencePageProjection:
    """Join exact producer evidence into complete canonical pages."""
    if type(request) is not ReadingEvidenceProjectionRequest:
        raise TypeError("request must be ReadingEvidenceProjectionRequest")
    used_clean: set[ReadingEvidenceIdentity] = set()
    used_figures: set[ReadingEvidenceIdentity] = set()
    used_tables: set[ReadingEvidenceIdentity] = set()
    used_equations: set[ReadingEvidenceIdentity] = set()
    blocks_by_page: dict[int, list[ReadingEvidenceBlock]] = {
        index: [] for index in range(len(request.page_text))
    }
    for item in request.structured_items:
        if item.kind in (
            ReadingStructuredItemKind.PARAGRAPH,
            ReadingStructuredItemKind.HEADING,
        ):
            text_block = project_reading_text_evidence_block(
                item=item,
                clean_text=request.clean_text,
                basis=request.configuration.text_basis,
            )
            source_ids = {value.record_id for value in text_block.sources}
            if used_clean.intersection(source_ids):
                raise ReadingEvidenceError(
                    "clean-text evidence is multiply used"
                )
            used_clean.update(source_ids)
            block: ReadingEvidenceBlock = text_block
        elif item.kind is ReadingStructuredItemKind.FIGURE:
            figure_block = project_reading_figure_evidence_block(
                item=item,
                figures=request.figures,
                configuration=request.configuration,
                caption_basis=request.configuration.caption_basis,
            )
            figure_id = figure_block.producer_evidence.record_id
            if figure_id in used_figures:
                raise ReadingEvidenceError(
                    "figure producer evidence is multiply used"
                )
            used_figures.add(figure_id)
            block = figure_block
        elif item.kind is ReadingStructuredItemKind.TABLE:
            table_block = project_reading_table_evidence_block(
                item=item,
                tables=request.tables,
                configuration=request.configuration,
            )
            table_id = table_block.producer_evidence.record_id
            if table_id in used_tables:
                raise ReadingEvidenceError(
                    "table producer evidence is multiply used"
                )
            used_tables.add(table_id)
            block = table_block
        elif item.kind is ReadingStructuredItemKind.EQUATION:
            equation_block = project_reading_equation_evidence_block(
                item=item,
                equations=request.equations,
                disposition=request.configuration.equation_disposition,
            )
            equation_id = equation_block.producer_evidence.record_id
            if equation_id in used_equations:
                raise ReadingEvidenceError(
                    "equation producer evidence is multiply used"
                )
            used_equations.add(equation_id)
            block = equation_block
        else:
            raise TypeError("structured item kind is unsupported")
        blocks_by_page[item.page_location.physical_page_index].append(block)
    if used_clean != {value.record_id for value in request.clean_text}:
        raise ReadingEvidenceError("clean-text evidence coverage is incomplete")
    pages = ReadingEvidencePageInventory(
        *(
            ReadingEvidencePage(
                page_text=page_text,
                blocks=ReadingEvidenceBlockInventory(*blocks_by_page[index]),
            )
            for index, page_text in enumerate(request.page_text)
        )
    )
    return ReadingEvidencePageProjection(
        pages=pages,
        clean_text_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.CLEAN_TEXT,
            *sorted(used_clean, key=lambda value: value.value),
        ),
        figure_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.FIGURE,
            *sorted(used_figures, key=lambda value: value.value),
        ),
        table_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.TABLE,
            *sorted(used_tables, key=lambda value: value.value),
        ),
        equation_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.EQUATION,
            *sorted(used_equations, key=lambda value: value.value),
        ),
    )
