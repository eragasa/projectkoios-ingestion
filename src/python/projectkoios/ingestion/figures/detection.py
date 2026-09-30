"""Deterministic figure candidate planning and materialization."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from io import BytesIO
from typing import BinaryIO, Protocol

from projectkoios.ingestion.figures.contracts import (
    _FIGURE_CAPTION,
    _LEGEND,
    _SUBFIGURE_LABEL,
    EmbeddedFigureArtifact,
    FigureArtifactKind,
    FigureAssociationRole,
    FigureCandidate,
    FigureComponent,
    FigureDetectionConfiguration,
    FigureDetectionInput,
    FigureDetectionLimitError,
    FigureDetectionResult,
    FigureDrawingEvidence,
    FigureEvidenceStatus,
    FigureTextAssociation,
    _axis_gap,
    _box_area,
    _boxes_within,
    _decimal,
    _FigureInspector,
    _near_box,
    _optional_block_box,
    _padded_box,
    _PageRegionRenderer,
    _source_label,
    _union_boxes,
    _union_boxes_allowing_extents,
    _validate_rendered_aggregate,
)
from projectkoios.ingestion.figures.inspection import _read_exact_payload
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout import PageLayoutResult
from projectkoios.ingestion.models import (
    BoundingBox,
    ExtractedBlock,
    ExtractedDocument,
    IngestionWarning,
    Metadata,
    SourceSpan,
    WarningSeverity,
)
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RenderedRegion,
)


class _DetectorContext(Protocol):
    name: str
    version: str
    configuration: FigureDetectionConfiguration
    region_renderer: _PageRegionRenderer
    figure_inspector: _FigureInspector

    @property
    def configuration_digest(self) -> str: ...


@dataclass(frozen=True)
class _Visual:
    key: str
    page_index: int
    kind: FigureArtifactKind
    box: BoundingBox
    artifact: EmbeddedFigureArtifact | None
    drawings: tuple[FigureDrawingEvidence, ...]
    caption_block: ExtractedBlock | None
    caption_distance: float | None
    selection: PageRegionSelection | None


@dataclass(frozen=True)
class _CandidatePlan:
    page_index: int
    visuals: tuple[_Visual, ...]
    caption_block: ExtractedBlock | None


@dataclass(frozen=True)
class _WarningSpec:
    code: str
    message: str
    source_spans: tuple[SourceSpan, ...]
    evidence: Metadata = ()


class _DeterministicFigureCandidateDetector:
    def detect_with_layout(
        self: _DetectorContext,
        document: ExtractedDocument,
        content: BinaryIO,
        layouts: tuple[PageLayoutResult, ...],
    ) -> FigureDetectionResult:
        payload = _read_exact_payload(
            document.source, content, self.configuration
        )
        page_evidence = self.figure_inspector.inspect(
            document, BytesIO(payload), self.configuration
        )
        detection_input = FigureDetectionInput.create(
            document=document,
            layouts=layouts,
            page_evidence=page_evidence,
            configuration=self.configuration,
        )
        caption_comparisons = sum(
            (len(evidence.embedded_artifacts) + len(evidence.drawings))
            * sum(
                block.kind == "text"
                and block.text is not None
                and _FIGURE_CAPTION.match(block.text) is not None
                for block in page.blocks
            )
            for page, evidence in zip(
                document.pages, page_evidence, strict=True
            )
        )
        if caption_comparisons > self.configuration.max_association_comparisons:
            raise FigureDetectionLimitError(
                "association comparisons exceed max_association_comparisons"
            )
        plans, ignored_specs = _plan_candidates(detection_input)
        if len(plans) > self.configuration.max_candidates:
            raise FigureDetectionLimitError("figures exceed max_candidates")
        component_count = sum(len(plan.visuals) for plan in plans)
        if component_count > self.configuration.max_components:
            raise FigureDetectionLimitError("components exceed max_components")
        text_counts = {
            page.page_index: sum(block.kind == "text" for block in page.blocks)
            for page in document.pages
        }
        association_comparisons = caption_comparisons + sum(
            len(plan.visuals) * text_counts[plan.page_index] for plan in plans
        )
        if (
            association_comparisons
            > self.configuration.max_association_comparisons
        ):
            raise FigureDetectionLimitError(
                "association comparisons exceed max_association_comparisons"
            )
        selections = tuple(
            visual.selection
            for plan in plans
            for visual in plan.visuals
            if visual.selection is not None
        )
        rendered_by_selection: dict[PageRegionSelection, RenderedRegion] = {}
        if selections:
            rendered = self.region_renderer.render(
                document.source, BytesIO(payload), selections
            )
            if len(rendered) != len(selections):
                raise ValueError("renderer returned an unexpected result count")
            for selection, region in zip(selections, rendered, strict=True):
                previous = rendered_by_selection.get(selection)
                if previous is not None and previous != region:
                    raise ValueError(
                        "renderer returned inconsistent duplicate selections"
                    )
                rendered_by_selection[selection] = region
            _validate_rendered_aggregate(
                tuple(rendered_by_selection.values()), self.configuration
            )
        candidates: list[FigureCandidate] = []
        candidate_specs: list[list[_WarningSpec]] = []
        for plan in plans:
            components = tuple(
                _component_from_visual(
                    detection_input,
                    visual,
                    component_index,
                    rendered_by_selection,
                    self.name,
                    self.version,
                )
                for component_index, visual in enumerate(plan.visuals)
            )
            associations = _associations_for_plan(
                detection_input, plan, components
            )
            source_spans = tuple(
                span
                for component in components
                for span in component.source_spans
            )
            caption = next(
                (
                    association
                    for association in associations
                    if association.role is FigureAssociationRole.CAPTION
                ),
                None,
            )
            source_label = (
                _source_label(caption.text) if caption is not None else None
            )
            plan_specs: list[_WarningSpec] = []
            confidence = min(component.confidence for component in components)
            if caption is None:
                confidence = max(0.0, confidence - 0.25)
                plan_specs.append(
                    _WarningSpec(
                        code="figure.caption_missing",
                        message=(
                            "Embedded figure evidence has no associated caption"
                        ),
                        source_spans=source_spans,
                    )
                )
            else:
                confidence = min(1.0, confidence + 0.08)
            if confidence < self.configuration.proposed_confidence_threshold:
                plan_specs.append(
                    _WarningSpec(
                        code="figure.low_confidence",
                        message=(
                            "Figure confidence is below the configured "
                            "proposal threshold"
                        ),
                        source_spans=source_spans,
                    )
                )
            status = (
                FigureEvidenceStatus.AMBIGUOUS
                if plan_specs
                else FigureEvidenceStatus.PROPOSED
            )
            box = _union_boxes(
                tuple(component.source_bounding_box for component in components)
            )
            candidate = FigureCandidate.create(
                detection_input_id=detection_input.input_id,
                page_index=plan.page_index,
                source_label=source_label,
                source_bounding_box=box,
                components=components,
                associations=associations,
                source_spans=source_spans,
                evidence_status=status,
                confidence=confidence,
                evidence=(
                    ("component_count", str(len(components))),
                    ("caption_present", str(caption is not None).lower()),
                ),
                warning_ids=(),
                processor_name=self.name,
                processor_version=self.version,
                configuration_digest=self.configuration_digest,
            )
            candidates.append(candidate)
            candidate_specs.append(plan_specs)
        if (
            len(ignored_specs) + sum(len(specs) for specs in candidate_specs)
            > self.configuration.max_warnings
        ):
            raise FigureDetectionLimitError("warnings exceed max_warnings")
        warnings, final_candidates = _materialize_warnings(
            tuple(candidates), tuple(candidate_specs), ignored_specs
        )
        if len(warnings) > self.configuration.max_warnings:
            raise FigureDetectionLimitError("warnings exceed max_warnings")
        return FigureDetectionResult.create(
            detection_input=detection_input,
            candidates=final_candidates,
            warnings=warnings,
            processor_name=self.name,
            processor_version=self.version,
        )


def _plan_candidates(
    detection_input: FigureDetectionInput,
) -> tuple[tuple[_CandidatePlan, ...], tuple[_WarningSpec, ...]]:
    configuration = detection_input.configuration
    document = detection_input.document
    evidence_by_page = {
        evidence.page_index: evidence
        for evidence in detection_input.page_evidence
    }
    plans: list[_CandidatePlan] = []
    ignored: list[_WarningSpec] = []
    for page in document.pages:
        evidence = evidence_by_page[page.page_index]
        text_blocks = tuple(
            block for block in page.blocks if block.kind == "text"
        )
        captions = tuple(
            block
            for block in text_blocks
            if block.text is not None and _FIGURE_CAPTION.match(block.text)
        )
        visuals: list[_Visual] = []
        for artifact in evidence.embedded_artifacts:
            caption, distance = _nearest_caption(
                artifact.source_bounding_box, captions, configuration
            )
            visuals.append(
                _Visual(
                    key=artifact.artifact_id,
                    page_index=page.page_index,
                    kind=FigureArtifactKind.EMBEDDED_IMAGE,
                    box=artifact.source_bounding_box,
                    artifact=artifact,
                    drawings=(),
                    caption_block=caption,
                    caption_distance=distance,
                    selection=None,
                )
            )
        for group in _drawing_groups(evidence.drawings, configuration):
            box = _union_boxes(
                tuple(item.source_bounding_box for item in group)
            )
            caption, distance = _nearest_caption(box, captions, configuration)
            if caption is None:
                if len(ignored) >= configuration.max_warnings:
                    raise FigureDetectionLimitError(
                        "warnings exceed max_warnings"
                    )
                ignored.append(
                    _WarningSpec(
                        code="figure.unassociated_drawing_ignored",
                        message=(
                            "Drawing evidence without a nearby explicit figure "
                            "caption was not promoted"
                        ),
                        source_spans=tuple(item.source_span for item in group),
                        evidence=(("page_index", str(page.page_index)),),
                    )
                )
                continue
            selection_box = _padded_box(
                box,
                page,
                configuration.render_padding_points,
            )
            selection = PageRegionSelection.for_bounding_box(
                document.source, page.page_index, selection_box
            )
            key = stable_id(
                "drawing-visual",
                tuple(item.drawing_id for item in group),
                selection.identity_parts(),
            )
            visuals.append(
                _Visual(
                    key=key,
                    page_index=page.page_index,
                    kind=FigureArtifactKind.RENDERED_DRAWING,
                    box=box,
                    artifact=None,
                    drawings=group,
                    caption_block=caption,
                    caption_distance=distance,
                    selection=selection,
                )
            )
        grouped: dict[str, list[_Visual]] = {}
        captions_by_key: dict[str, ExtractedBlock | None] = {}
        for visual in visuals:
            key = (
                visual.caption_block.block_id
                if visual.caption_block is not None
                else visual.key
            )
            grouped.setdefault(key, []).append(visual)
            captions_by_key[key] = visual.caption_block
        for key, items in grouped.items():
            plans.append(
                _CandidatePlan(
                    page_index=page.page_index,
                    visuals=tuple(
                        sorted(
                            items,
                            key=lambda item: (
                                item.box[1],
                                item.box[0],
                                item.key,
                            ),
                        )
                    ),
                    caption_block=captions_by_key[key],
                )
            )
        matched_caption_ids = {
            visual.caption_block.block_id
            for visual in visuals
            if visual.caption_block is not None
        }
        for caption in captions:
            if caption.block_id not in matched_caption_ids:
                if len(ignored) >= configuration.max_warnings:
                    raise FigureDetectionLimitError(
                        "warnings exceed max_warnings"
                    )
                ignored.append(
                    _WarningSpec(
                        code="figure.caption_without_visual",
                        message=(
                            "An explicit figure caption has no nearby embedded "
                            "or drawing evidence"
                        ),
                        source_spans=caption.source_spans,
                    )
                )
    plans.sort(
        key=lambda plan: (
            plan.page_index,
            min(visual.box[1] for visual in plan.visuals),
            min(visual.box[0] for visual in plan.visuals),
        )
    )
    return tuple(plans), tuple(ignored)


def _component_from_visual(
    detection_input: FigureDetectionInput,
    visual: _Visual,
    component_index: int,
    rendered_by_selection: dict[PageRegionSelection, RenderedRegion],
    processor_name: str,
    processor_version: str,
) -> FigureComponent:
    source_block_ids: tuple[str, ...]
    source_spans: tuple[SourceSpan, ...]
    if visual.artifact is not None:
        source_block_ids = (visual.artifact.source_block_id,)
        source_spans = visual.artifact.source_spans
        artifact_id = visual.artifact.artifact_id
        drawing_ids: tuple[str, ...] = ()
        rendered = None
        confidence = 0.92
        evidence: Metadata = (("method", "embedded_image_bytes"),)
    else:
        if visual.selection is None:
            raise ValueError("drawing visual lacks a render selection")
        source_block_ids = ()
        source_spans = tuple(item.source_span for item in visual.drawings)
        artifact_id = None
        drawing_ids = tuple(item.drawing_id for item in visual.drawings)
        rendered = rendered_by_selection[visual.selection]
        confidence = 0.78
        evidence = (("method", "rendered_pdf_drawing_commands"),)
    return FigureComponent.create(
        detection_input_id=detection_input.input_id,
        page_index=visual.page_index,
        component_index=component_index,
        artifact_kind=visual.kind,
        source_bounding_box=visual.box,
        source_block_ids=source_block_ids,
        source_spans=source_spans,
        embedded_artifact_id=artifact_id,
        drawing_evidence_ids=drawing_ids,
        rendered_region=rendered,
        evidence_status=FigureEvidenceStatus.PROPOSED,
        confidence=confidence,
        evidence=evidence,
        warning_ids=(),
        processor_name=processor_name,
        processor_version=processor_version,
        configuration_digest=detection_input.configuration.configuration_digest,
    )


def _associations_for_plan(
    detection_input: FigureDetectionInput,
    plan: _CandidatePlan,
    components: tuple[FigureComponent, ...],
) -> tuple[FigureTextAssociation, ...]:
    page = detection_input.document.pages[plan.page_index]
    associations: list[FigureTextAssociation] = []
    used_blocks: set[str] = set()
    if plan.caption_block is not None:
        distance = min(
            visual.caption_distance
            for visual in plan.visuals
            if visual.caption_distance is not None
        )
        distance_text = _decimal(float(distance))
        retained_distance = float(distance_text)
        associations.append(
            FigureTextAssociation.create(
                role=FigureAssociationRole.CAPTION,
                page_index=plan.page_index,
                block=plan.caption_block,
                component_id=None,
                confidence=max(0.70, 1.0 - retained_distance / 720.0),
                evidence=(
                    ("method", "explicit_figure_prefix_and_geometry"),
                    ("distance_points", distance_text),
                ),
            )
        )
        used_blocks.add(plan.caption_block.block_id)
    for component in components:
        for block in page.blocks:
            if (
                block.kind != "text"
                or block.text is None
                or block.block_id in used_blocks
            ):
                continue
            box = _optional_block_box(block)
            if box is None:
                continue
            role: FigureAssociationRole | None = None
            if _SUBFIGURE_LABEL.match(block.text) and _near_box(
                box,
                component.source_bounding_box,
                detection_input.configuration.association_distance_points / 2.0,
            ):
                role = FigureAssociationRole.SUBFIGURE_LABEL
            elif (
                len(block.text)
                <= detection_input.configuration.maximum_legend_characters
                and _LEGEND.match(block.text)
                and _near_box(
                    box,
                    component.source_bounding_box,
                    detection_input.configuration.association_distance_points
                    / 4.0,
                )
            ):
                role = FigureAssociationRole.LEGEND
            if role is None:
                continue
            associations.append(
                FigureTextAssociation.create(
                    role=role,
                    page_index=plan.page_index,
                    block=block,
                    component_id=component.component_id,
                    confidence=(
                        0.88
                        if role is FigureAssociationRole.SUBFIGURE_LABEL
                        else 0.76
                    ),
                    evidence=(
                        ("method", "source_text_and_component_geometry"),
                    ),
                )
            )
            used_blocks.add(block.block_id)
    if len(associations) > detection_input.configuration.max_associations:
        raise FigureDetectionLimitError("associations exceed max_associations")
    return tuple(associations)


def _drawing_groups(
    drawings: tuple[FigureDrawingEvidence, ...],
    configuration: FigureDetectionConfiguration,
) -> tuple[tuple[FigureDrawingEvidence, ...], ...]:
    if not drawings:
        return ()
    gap = configuration.drawing_group_gap_points
    cell_size = max(gap, 1.0)
    spatial: dict[tuple[int, int], list[int]] = {}
    parents = list(range(len(drawings)))
    comparisons = 0

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    def cells_for(
        box: BoundingBox, *, padding: float
    ) -> tuple[tuple[int, int], ...]:
        x0, y0, x1, y1 = box
        first_x = math.floor((x0 - padding) / cell_size)
        last_x = math.floor((x1 + padding) / cell_size)
        first_y = math.floor((y0 - padding) / cell_size)
        last_y = math.floor((y1 + padding) / cell_size)
        return tuple(
            (x, y)
            for x in range(first_x, last_x + 1)
            for y in range(first_y, last_y + 1)
        )

    for index, drawing in enumerate(drawings):
        candidates = {
            prior
            for cell in cells_for(drawing.source_bounding_box, padding=0.0)
            for prior in spatial.get(cell, ())
        }
        touched_roots: set[int] = set()
        for prior in sorted(candidates):
            root = find(prior)
            if root in touched_roots:
                continue
            comparisons += 1
            if comparisons > configuration.max_drawing_group_comparisons:
                raise FigureDetectionLimitError(
                    "drawing grouping exceeds max_drawing_group_comparisons"
                )
            if _boxes_within(
                drawing.source_bounding_box,
                drawings[prior].source_bounding_box,
                gap,
            ):
                union(index, prior)
                touched_roots.add(root)
        for cell in cells_for(drawing.source_bounding_box, padding=gap):
            spatial.setdefault(cell, []).append(index)

    grouped: dict[int, list[FigureDrawingEvidence]] = {}
    for index, drawing in enumerate(drawings):
        grouped.setdefault(find(index), []).append(drawing)
    retained: list[tuple[FigureDrawingEvidence, ...]] = []
    for group in grouped.values():
        ordered = tuple(sorted(group, key=lambda item: item.source_object_id))
        box = _union_boxes_allowing_extents(
            tuple(item.source_bounding_box for item in ordered)
        )
        if (
            box[2] - box[0] < configuration.minimum_drawing_dimension_points
            or box[3] - box[1] < configuration.minimum_drawing_dimension_points
            or _box_area(box) < configuration.minimum_drawing_area_points
        ):
            continue
        retained.append(ordered)
    return tuple(retained)


def _nearest_caption(
    visual_box: BoundingBox,
    captions: tuple[ExtractedBlock, ...],
    configuration: FigureDetectionConfiguration,
) -> tuple[ExtractedBlock | None, float | None]:
    ranked: list[tuple[float, str, ExtractedBlock]] = []
    for caption in captions:
        box = _optional_block_box(caption)
        if box is None:
            continue
        vertical = _axis_gap(visual_box[1], visual_box[3], box[1], box[3])
        horizontal = _axis_gap(visual_box[0], visual_box[2], box[0], box[2])
        distance = vertical + horizontal * 0.5
        if distance <= configuration.association_distance_points:
            ranked.append((distance, caption.block_id, caption))
    if not ranked:
        return None, None
    ranked.sort(key=lambda value: (value[0], value[1]))
    return ranked[0][2], ranked[0][0]


def _materialize_warnings(
    candidates: tuple[FigureCandidate, ...],
    candidate_specs: tuple[list[_WarningSpec], ...],
    ignored_specs: tuple[_WarningSpec, ...],
) -> tuple[tuple[IngestionWarning, ...], tuple[FigureCandidate, ...]]:
    warnings: list[IngestionWarning] = []
    warning_ids_by_candidate: dict[str, list[str]] = {}
    for candidate, specs in zip(candidates, candidate_specs, strict=True):
        for spec in specs:
            warning = IngestionWarning.create(
                code=spec.code,
                severity=WarningSeverity.WARNING,
                message=spec.message,
                object_ids=(candidate.candidate_id,),
                source_spans=spec.source_spans,
                evidence=spec.evidence,
            )
            warnings.append(warning)
            warning_ids_by_candidate.setdefault(
                candidate.candidate_id, []
            ).append(warning.warning_id)
    for spec in ignored_specs:
        warnings.append(
            IngestionWarning.create(
                code=spec.code,
                severity=WarningSeverity.INFO,
                message=spec.message,
                source_spans=spec.source_spans,
                evidence=spec.evidence,
            )
        )
    final = tuple(
        replace(
            candidate,
            warning_ids=tuple(
                warning_ids_by_candidate.get(candidate.candidate_id, ())
            ),
        )
        for candidate in candidates
    )
    return tuple(warnings), final


def detect_figure_candidates(
    detector: _DetectorContext,
    document: ExtractedDocument,
    content: BinaryIO,
    layouts: tuple[PageLayoutResult, ...],
) -> FigureDetectionResult:
    """Run detection using dependencies owned by the public facade."""
    return _DeterministicFigureCandidateDetector.detect_with_layout(
        detector, document, content, layouts
    )
