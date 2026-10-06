"""Deterministic native-stream derivation."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from projectkoios.ingestion.reconciliation.limit.definition import (
    _LINE_BOUNDARIES,
)
from projectkoios.ingestion.reconciliation.limit.error import (
    OCRReconciliationLimitError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.reconciliation.configuration import (
        OCRReconciliationConfiguration,
    )
    from projectkoios.ingestion.reconciliation.evidence.native.block import (
        OCRNativeBlockEvidence,
    )
    from projectkoios.ingestion.reconciliation.request import (
        OCRReconciliationRequest,
    )
    from projectkoios.ingestion.reconciliation.segment.native.line import (
        OCRNativeLineSegment,
    )
from projectkoios.ingestion.reconciliation.validation import value as primitives


def _native_stream(
    reconciliation_input: OCRReconciliationRequest,
) -> tuple[OCRNativeBlockEvidence, ...]:
    from projectkoios.ingestion.reconciliation.evidence.native.block import (
        OCRNativeBlockEvidence,
    )

    if (
        reconciliation_input.native_page is None
        or reconciliation_input.layout_result is None
    ):
        return ()
    page = reconciliation_input.native_page
    layout = reconciliation_input.layout_result
    selected = set(reconciliation_input.selection.native_text_block_ids)
    raw_order = {
        block.block_id: index for index, block in enumerate(page.blocks)
    }
    proposed = {
        block_id: index for index, block_id in enumerate(layout.proposed_order)
    }
    block_by_id = {block.block_id: block for block in page.blocks}
    ordered_ids = sorted(
        selected,
        key=lambda block_id: (
            0 if block_id in proposed else 1,
            proposed.get(block_id, raw_order[block_id]),
            raw_order[block_id],
        ),
    )
    return tuple(
        OCRNativeBlockEvidence.from_block(block_by_id[block_id], order=order)
        for order, block_id in enumerate(ordered_ids)
    )


def _native_segments(
    native_stream: tuple[OCRNativeBlockEvidence, ...],
    configuration: OCRReconciliationConfiguration,
) -> tuple[OCRNativeLineSegment, ...]:
    from projectkoios.ingestion.reconciliation.segment.native.line import (
        OCRNativeLineSegment,
    )

    segments: list[OCRNativeLineSegment] = []
    total_text = 0
    for block in native_stream:
        for (
            line_index,
            raw_line,
        ) in _iter_text_lines(block.text):
            if not raw_line.strip():
                continue
            primitives._bounded_text(
                "native line text",
                raw_line,
                nonempty=True,
                limit=configuration.max_text_characters_per_item,
            )
            total_text += len(raw_line)
            if total_text > configuration.max_total_text_characters:
                raise OCRReconciliationLimitError(
                    "native segments exceed max_total_text_characters"
                )
            if len(segments) >= configuration.max_native_segments:
                raise OCRReconciliationLimitError(
                    "native segments exceed max_native_segments"
                )
            segment = OCRNativeLineSegment.create(
                block=block,
                line_index=line_index,
                text=raw_line,
                order=len(segments),
            )
            if (
                len(segment.normalized_text)
                > configuration.max_text_characters_per_item
            ):
                raise OCRReconciliationLimitError(
                    "normalized native text exceeds its configured limit"
                )
            segments.append(segment)
    return tuple(segments)


def _iter_text_lines(value: str) -> Iterator[tuple[int, str]]:
    if not value:
        yield 0, ""
        return
    start = 0
    line_index = 0
    position = 0
    while position < len(value):
        character = value[position]
        if character not in _LINE_BOUNDARIES:
            position += 1
            continue
        yield line_index, value[start:position]
        if (
            character == "\r"
            and position + 1 < len(value)
            and value[position + 1] == "\n"
        ):
            position += 1
        position += 1
        start = position
        line_index += 1
    if start < len(value):
        yield line_index, value[start:]
