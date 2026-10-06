"""Deterministic equation assembly from detector evidence."""

from __future__ import annotations

import re
from io import BytesIO

from projectkoios.ingestion.equations.assembly.identity import (
    EQUATION_ASSEMBLY_CONTRACT_VERSION,
    equation_assembly_id,
)
from projectkoios.ingestion.equations.assembly.kind import EquationAssemblyKind
from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.equations.assembly.result import (
    EquationAssemblyResult,
)
from projectkoios.ingestion.equations.assembly.text import (
    sanitize_equation_native_text,
)
from projectkoios.ingestion.equations.detection import (
    EquationCandidate,
    EquationCandidateKind,
    EquationDetectionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import BoundingBox, ExtractedPage, SourceSpan
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RenderedRegion,
)
from projectkoios.ingestion.pdf.renderer import PageRegionRenderer
from projectkoios.ingestion.sha256.verifier import SHA256Verifier

_COORDINATE_TUPLE = re.compile(
    r"(?:\d+\s*=\s*\d+\s*[,;]\s*){2,}\d+", re.IGNORECASE
)
_IO_FALSE_POSITIVE = re.compile(r"\bI\s*=\s*O\b", re.IGNORECASE)
_MATH_SIGNAL = re.compile(r"[=≈≃≤≥≠∝∑∫√∂∇∞±→←∏⋅·^_]|\\[A-Za-z]+")


class DeterministicEquationAssembler:
    """Group same-line display fragments and preserve all evidence layers."""

    def __init__(self, *, renderer: PageRegionRenderer) -> None:
        self.renderer = renderer

    def assemble(
        self,
        detection: EquationDetectionResult,
        content: bytes,
    ) -> EquationAssemblyResult:
        """Assemble and render bounded equation candidates."""

        document = detection.detection_input.document
        if not SHA256Verifier.verify(
            content=content, expected=document.source.content_hash
        ):
            raise ValueError("equation assembly requires exact PDF bytes")
        block_text = {
            block.block_id: block.text
            for page in document.pages
            for block in page.blocks
            if block.text is not None
        }
        groups = _candidate_groups(detection)
        selections = tuple(
            PageRegionSelection.for_bounding_box(
                document.source,
                group[0].rendered_region.page_index,
                _assembly_box(
                    group,
                    document.pages[group[0].rendered_region.page_index],
                ),
            )
            for group in groups
        )
        rendered = (
            self.renderer.render(
                document.source,
                BytesIO(content),
                selections,
            )
            if selections
            else ()
        )
        assemblies = tuple(
            _assembly_from_group(detection, group, region, block_text)
            for group, region in zip(groups, rendered, strict=True)
        )
        artifact_id = stable_id(
            "equation-assembly-artifact",
            EQUATION_ASSEMBLY_CONTRACT_VERSION,
            document.source.source_id,
            document.source.content_hash,
            document.document_id,
            detection.result_id,
            tuple(item.assembly_id for item in assemblies),
        )
        return EquationAssemblyResult(
            artifact_id=artifact_id,
            source_id=document.source.source_id,
            source_content_hash=document.source.content_hash,
            document_id=document.document_id,
            detection_result_id=detection.result_id,
            assemblies=assemblies,
        )


def _candidate_groups(
    detection: EquationDetectionResult,
) -> tuple[tuple[EquationCandidate, ...], ...]:
    by_page: dict[int, list[EquationCandidate]] = {}
    for candidate in detection.candidates:
        by_page.setdefault(candidate.rendered_region.page_index, []).append(
            candidate
        )
    groups: list[tuple[EquationCandidate, ...]] = []
    for page_index in sorted(by_page):
        values = by_page[page_index]
        displays = sorted(
            (
                item
                for item in values
                if item.kind is EquationCandidateKind.DISPLAY
            ),
            key=lambda item: (
                item.rendered_region.source_bounding_box[1],
                item.rendered_region.source_bounding_box[0],
                item.candidate_id,
            ),
        )
        page_width = detection.detection_input.document.pages[page_index].width
        remaining = list(displays)
        while remaining:
            group = [remaining.pop(0)]
            changed = True
            while changed:
                changed = False
                group_box = _union_boxes(
                    tuple(
                        item.rendered_region.source_bounding_box
                        for item in group
                    )
                )
                for candidate in tuple(remaining):
                    box = candidate.rendered_region.source_bounding_box
                    if _same_equation_line(group_box, box, page_width):
                        group.append(candidate)
                        remaining.remove(candidate)
                        changed = True
            groups.append(
                tuple(
                    sorted(
                        group,
                        key=lambda item: (
                            item.rendered_region.source_bounding_box[0]
                        ),
                    )
                )
            )
        groups.extend(
            (candidate,)
            for candidate in sorted(
                (
                    item
                    for item in values
                    if item.kind is EquationCandidateKind.INLINE
                ),
                key=lambda item: (
                    item.rendered_region.source_bounding_box[1],
                    item.rendered_region.source_bounding_box[0],
                    item.candidate_id,
                ),
            )
        )
    return tuple(groups)


def _same_equation_line(
    first: BoundingBox,
    second: BoundingBox,
    page_width: float,
) -> bool:
    midpoint = page_width / 2.0
    if (first[2] <= midpoint and second[0] >= midpoint) or (
        second[2] <= midpoint and first[0] >= midpoint
    ):
        return False
    overlap = min(first[3], second[3]) - max(first[1], second[1])
    minimum_height = min(first[3] - first[1], second[3] - second[1])
    if overlap <= 0.2 * minimum_height:
        return False
    horizontal_gap = max(first[0], second[0]) - min(first[2], second[2])
    return horizontal_gap <= max(48.0, page_width * 0.14)


def _assembly_box(
    group: tuple[EquationCandidate, ...],
    page: ExtractedPage,
) -> BoundingBox:
    boxes = list(item.rendered_region.source_bounding_box for item in group)
    union = _union_boxes(tuple(boxes))
    changed = True
    while changed:
        changed = False
        for block in page.blocks:
            if block.text is None or not _looks_like_math_fragment(block.text):
                continue
            block_box = _block_box(block.source_spans)
            if block_box is None or block_box in boxes:
                continue
            if not _same_equation_line(union, block_box, page.width):
                continue
            boxes.append(block_box)
            union = _union_boxes(tuple(boxes))
            changed = True
    return (
        max(0.0, union[0] - 3.0),
        max(0.0, union[1] - 3.0),
        min(page.width, union[2] + 3.0),
        min(page.height, union[3] + 3.0),
    )


def _block_box(spans: tuple[SourceSpan, ...]) -> BoundingBox | None:
    boxes = tuple(
        span.bounding_box for span in spans if span.bounding_box is not None
    )
    return _union_boxes(boxes) if boxes else None


def _looks_like_math_fragment(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized or len(normalized) > 512:
        return False
    if len(normalized.split()) > 12:
        return False
    return len(normalized) <= 24 or bool(_MATH_SIGNAL.search(normalized))


def _assembly_from_group(
    detection: EquationDetectionResult,
    group: tuple[EquationCandidate, ...],
    region: RenderedRegion,
    block_text: dict[str, str],
) -> EquationAssembly:
    candidate_ids = tuple(item.candidate_id for item in group)
    raw_fragments = tuple(item.raw_text for item in group)
    joined = " ".join(
        fragment.strip() for fragment in raw_fragments if fragment.strip()
    )
    sanitized, control_count = sanitize_equation_native_text(joined)
    labels = tuple(
        item.source_label for item in group if item.source_label is not None
    )
    source_spans = tuple(span for item in group for span in item.source_spans)
    block_ids = tuple(dict.fromkeys(item.source_block_id for item in group))
    first = group[0]
    last = group[-1]
    preceding_id = (
        first.preceding_context.block_id if first.preceding_context else None
    )
    following_id = (
        last.following_context.block_id if last.following_context else None
    )
    reasons: list[str] = []
    rejected = False
    if control_count:
        reasons.append("control_characters_sanitized")
    if _IO_FALSE_POSITIVE.search(sanitized):
        reasons.append("io_typographic_false_positive")
        rejected = True
    if _COORDINATE_TUPLE.search(sanitized) or (
        "to M" in sanitized and sanitized.count("=2") >= 2
    ):
        reasons.append("coordinate_tuple_false_positive")
        rejected = True
    kind = (
        EquationAssemblyKind.DISPLAY
        if any(item.kind is EquationCandidateKind.DISPLAY for item in group)
        else EquationAssemblyKind.INLINE
    )
    if kind is EquationAssemblyKind.INLINE:
        reasons.append("inline_context_only")
        if len(sanitized) > 80 or len(sanitized.split()) > 12:
            reasons.append("prose_relation")
    detector_statuses = tuple(item.evidence_status for item in group)
    assembly_id = equation_assembly_id(
        detection.result_id,
        candidate_ids,
        detector_statuses,
        region.region_id,
        sanitized,
        tuple(reasons),
        rejected,
    )
    return EquationAssembly(
        assembly_id=assembly_id,
        detection_result_id=detection.result_id,
        candidate_ids=candidate_ids,
        detector_evidence_statuses=detector_statuses,
        kind=kind,
        page_index=region.page_index,
        printed_page_label=region.printed_page_label,
        source_spans=source_spans,
        source_block_ids=block_ids,
        raw_fragments=raw_fragments,
        sanitized_native_text=sanitized,
        control_character_count=control_count,
        source_labels=labels,
        preceding_context_text=(
            block_text.get(preceding_id) if preceding_id else None
        ),
        following_context_text=(
            block_text.get(following_id) if following_id else None
        ),
        rendered_region=region,
        prefilter_reasons=tuple(reasons),
        rejected=rejected,
    )


def _union_boxes(boxes: tuple[BoundingBox, ...]) -> BoundingBox:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )
