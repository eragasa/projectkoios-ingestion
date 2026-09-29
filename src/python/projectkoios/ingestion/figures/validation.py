"""Cross-linked figure result and retained-resource validation."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum

from projectkoios.ingestion.figures import (
    _FIGURE_CAPTION,
    _LEGEND,
    _SUBFIGURE_LABEL,
    FigureArtifactKind,
    FigureAssociationRole,
    FigureComponent,
    FigureDetectionConfiguration,
    FigureDetectionInput,
    FigureDetectionLimitError,
    FigureDetectionResult,
    FigureEvidenceStatus,
    FigurePageEvidence,
    _axis_gap,
    _block_box,
    _box_within_page,
    _decimal,
    _identity_fields,
    _near_box,
    _require_tuple,
    _source_label,
    _union_boxes,
)
from projectkoios.ingestion.layout import LayoutBlockReference, PageLayoutResult
from projectkoios.ingestion.models import ExtractedDocument, WarningSeverity
from projectkoios.ingestion.pdf.models import RenderedRegion


def validate_input_parts(
    document: ExtractedDocument,
    layouts: tuple[PageLayoutResult, ...],
    page_evidence: tuple[FigurePageEvidence, ...],
    configuration: FigureDetectionConfiguration,
) -> None:
    if not isinstance(document, ExtractedDocument):
        raise TypeError("figure input document is unsupported")
    if not isinstance(configuration, FigureDetectionConfiguration):
        raise TypeError("figure configuration is unsupported")
    _require_tuple("figure layouts", layouts)
    _require_tuple("figure page evidence", page_evidence)
    if document.source.media_type != "application/pdf":
        raise ValueError("figure detection requires application/pdf")
    if document.source.byte_length > configuration.max_source_bytes:
        raise FigureDetectionLimitError("source exceeds max_source_bytes")
    if len(document.pages) > configuration.max_pages:
        raise FigureDetectionLimitError("pages exceed max_pages")
    if len(layouts) != len(document.pages) or len(page_evidence) != len(
        document.pages
    ):
        raise ValueError(
            "figure input requires one layout and page evidence per page"
        )
    block_count = sum(len(page.blocks) for page in document.pages)
    text_blocks = tuple(
        block
        for page in document.pages
        for block in page.blocks
        if block.kind == "text"
    )
    if block_count > configuration.max_input_blocks:
        raise FigureDetectionLimitError("blocks exceed max_input_blocks")
    if len(text_blocks) > configuration.max_text_blocks:
        raise FigureDetectionLimitError("text blocks exceed max_text_blocks")
    if (
        sum(len(block.text or "") for block in text_blocks)
        > configuration.max_text_characters
    ):
        raise FigureDetectionLimitError("text exceeds max_text_characters")
    span_count = sum(
        len(block.source_spans)
        for page in document.pages
        for block in page.blocks
    )
    if span_count > configuration.max_source_spans:
        raise FigureDetectionLimitError("source spans exceed max_source_spans")
    total_embedded_bytes = 0
    total_embedded_assets = 0
    total_drawings = 0
    for page, layout, evidence in zip(
        document.pages, layouts, page_evidence, strict=True
    ):
        if (
            layout.page_index != page.page_index
            or layout.source_id != document.source.source_id
            or layout.source_blob_id != document.source.blob_id
            or layout.source_content_hash != document.source.content_hash
            or layout.page_width != page.width
            or layout.page_height != page.height
            or layout.coordinate_system != page.coordinate_system
            or layout.rotation_degrees != page.rotation_degrees
            or layout.raw_block_ids
            != tuple(block.block_id for block in page.blocks)
            or layout.raw_blocks
            != tuple(
                LayoutBlockReference.from_block(block) for block in page.blocks
            )
        ):
            raise ValueError("figure layout evidence is stale or inconsistent")
        if (
            evidence.source_id != document.source.source_id
            or evidence.source_blob_id != document.source.blob_id
            or evidence.source_content_hash != document.source.content_hash
            or evidence.page_index != page.page_index
            or evidence.page_width != page.width
            or evidence.page_height != page.height
            or evidence.rotation_degrees != page.rotation_degrees
            or evidence.coordinate_system != page.coordinate_system
        ):
            raise ValueError("figure page evidence is stale or inconsistent")
        expected_image_ids = tuple(
            block.block_id for block in page.blocks if block.kind == "image"
        )
        if (
            tuple(
                artifact.source_block_id
                for artifact in evidence.embedded_artifacts
            )
            != expected_image_ids
        ):
            raise ValueError("figure embedded evidence is incomplete")
        block_by_id = {block.block_id: block for block in page.blocks}
        if len(
            {artifact.artifact_id for artifact in evidence.embedded_artifacts}
        ) != len(evidence.embedded_artifacts):
            raise ValueError("embedded artifact IDs must be unique")
        for artifact in evidence.embedded_artifacts:
            block = block_by_id[artifact.source_block_id]
            if (
                artifact.source_id != document.source.source_id
                or artifact.source_blob_id != document.source.blob_id
                or artifact.source_content_hash != document.source.content_hash
                or artifact.page_index != page.page_index
                or artifact.source_spans != block.source_spans
                or artifact.asset_id != block.asset_id
                or artifact.media_type != block.asset_media_type
                or artifact.mask_asset_id != block.asset_mask_id
                or artifact.mask_media_type != block.asset_mask_media_type
            ):
                raise ValueError(
                    "embedded artifact differs from raw image evidence"
                )
            if (
                artifact.byte_length > configuration.max_embedded_asset_bytes
                or (
                    artifact.mask_byte_length is not None
                    and artifact.mask_byte_length
                    > configuration.max_embedded_asset_bytes
                )
            ):
                raise FigureDetectionLimitError(
                    "embedded asset exceeds max_embedded_asset_bytes"
                )
            total_embedded_bytes += artifact.byte_length + (
                artifact.mask_byte_length or 0
            )
            total_embedded_assets += 1
        if len(evidence.drawings) > configuration.max_drawings_per_page:
            raise FigureDetectionLimitError(
                "retained drawings exceed their per-page limit"
            )
        if (
            len(evidence.drawings) + evidence.ignored_drawing_count
            > configuration.max_backend_drawings_per_page
        ):
            raise FigureDetectionLimitError(
                "backend drawings exceed their per-page limit"
            )
        if len({item.drawing_id for item in evidence.drawings}) != len(
            evidence.drawings
        ):
            raise ValueError("drawing evidence IDs must be unique")
        if (
            sum(item.item_count for item in evidence.drawings)
            > configuration.max_drawing_items_per_page
        ):
            raise FigureDetectionLimitError(
                "drawing items exceed max_drawing_items_per_page"
            )
        for drawing in evidence.drawings:
            if (
                drawing.source_id != document.source.source_id
                or drawing.source_blob_id != document.source.blob_id
                or drawing.page_index != page.page_index
                or not _box_within_page(drawing.source_bounding_box, page)
            ):
                raise ValueError("drawing evidence is stale or inconsistent")
        total_drawings += len(evidence.drawings)
    if total_embedded_assets > configuration.max_embedded_assets:
        raise FigureDetectionLimitError(
            "embedded assets exceed max_embedded_assets"
        )
    if total_embedded_bytes > configuration.max_total_embedded_bytes:
        raise FigureDetectionLimitError(
            "embedded assets exceed max_total_embedded_bytes"
        )
    if total_drawings > configuration.max_total_drawings:
        raise FigureDetectionLimitError("drawings exceed max_total_drawings")
    if span_count + total_drawings > configuration.max_source_spans:
        raise FigureDetectionLimitError("source spans exceed max_source_spans")


def validate_result(result: FigureDetectionResult) -> None:
    if not isinstance(result.detection_input, FigureDetectionInput):
        raise TypeError("figure result input is unsupported")
    _require_tuple("figure candidates", result.candidates)
    _require_tuple("figure warnings", result.warnings)
    configuration = result.detection_input.configuration
    if result.configuration_digest != configuration.configuration_digest:
        raise ValueError("figure result configuration is inconsistent")
    _identity_fields(result.processor_name, result.processor_version)
    if len(result.candidates) > configuration.max_candidates:
        raise FigureDetectionLimitError("figures exceed max_candidates")
    if len(result.warnings) > configuration.max_warnings:
        raise FigureDetectionLimitError("warnings exceed max_warnings")
    warning_ids = tuple(warning.warning_id for warning in result.warnings)
    if len(set(warning_ids)) != len(warning_ids):
        raise ValueError("figure warnings must be unique")
    candidate_ids = {candidate.candidate_id for candidate in result.candidates}
    if len(candidate_ids) != len(result.candidates):
        raise ValueError("figure candidate IDs must be unique")
    component_ids = {
        component.component_id
        for candidate in result.candidates
        for component in candidate.components
    }
    if len(component_ids) != sum(
        len(candidate.components) for candidate in result.candidates
    ):
        raise ValueError("figure component IDs must be unique")
    allowed_objects = candidate_ids | component_ids
    for warning in result.warnings:
        if any(
            object_id not in allowed_objects for object_id in warning.object_ids
        ):
            raise ValueError("figure warning references an unknown object")
        if warning.object_ids:
            if warning.severity is not WarningSeverity.WARNING:
                raise ValueError(
                    "candidate figure warning severity is inconsistent"
                )
        elif (
            warning.severity is not WarningSeverity.INFO
            or warning.code
            not in (
                "figure.unassociated_drawing_ignored",
                "figure.caption_without_visual",
            )
        ):
            raise ValueError("figure informational warning is inconsistent")
    block_by_id = {
        block.block_id: block
        for page in result.detection_input.document.pages
        for block in page.blocks
    }
    artifact_by_id = {
        artifact.artifact_id: artifact
        for page in result.detection_input.page_evidence
        for artifact in page.embedded_artifacts
    }
    drawing_by_id = {
        drawing.drawing_id: drawing
        for page in result.detection_input.page_evidence
        for drawing in page.drawings
    }
    total_components = 0
    total_associations = 0
    for candidate in result.candidates:
        if (
            candidate.detection_input_id != result.detection_input.input_id
            or candidate.processor_name != result.processor_name
            or candidate.processor_version != result.processor_version
            or candidate.configuration_digest != result.configuration_digest
        ):
            raise ValueError(
                "figure candidate derivation evidence is inconsistent"
            )
        linked_warnings = tuple(
            warning
            for warning in result.warnings
            if candidate.candidate_id in warning.object_ids
        )
        expected_warning_ids = tuple(
            warning.warning_id for warning in linked_warnings
        )
        if candidate.warning_ids != expected_warning_ids:
            raise ValueError("figure candidate warning links are incomplete")
        if tuple(
            component.component_index for component in candidate.components
        ) != tuple(range(len(candidate.components))):
            raise ValueError("figure component indexes are not contiguous")
        expected_spans = tuple(
            span
            for component in candidate.components
            for span in component.source_spans
        )
        if candidate.source_spans != expected_spans:
            raise ValueError("figure candidate source spans are inconsistent")
        if candidate.source_bounding_box != _union_boxes(
            tuple(
                component.source_bounding_box
                for component in candidate.components
            )
        ):
            raise ValueError("figure candidate bounds are inconsistent")
        page = result.detection_input.document.pages[candidate.page_index]
        if not _box_within_page(candidate.source_bounding_box, page):
            raise ValueError("figure candidate bounds exceed its page")
        for component in candidate.components:
            expected_component_warning_ids = tuple(
                warning.warning_id
                for warning in result.warnings
                if component.component_id in warning.object_ids
            )
            if component.warning_ids != expected_component_warning_ids:
                raise ValueError(
                    "figure component warning links are incomplete"
                )
            if (
                component.detection_input_id != result.detection_input.input_id
                or component.page_index != candidate.page_index
                or component.processor_name != result.processor_name
                or component.processor_version != result.processor_version
                or component.configuration_digest != result.configuration_digest
            ):
                raise ValueError(
                    "figure component derivation evidence is inconsistent"
                )
            expected_component_confidence = (
                0.92
                if component.artifact_kind is FigureArtifactKind.EMBEDDED_IMAGE
                else 0.78
            )
            expected_component_evidence = (
                (
                    "method",
                    (
                        "embedded_image_bytes"
                        if component.artifact_kind
                        is FigureArtifactKind.EMBEDDED_IMAGE
                        else "rendered_pdf_drawing_commands"
                    ),
                ),
            )
            if (
                component.evidence_status is not FigureEvidenceStatus.PROPOSED
                or component.confidence != expected_component_confidence
                or component.evidence != expected_component_evidence
            ):
                raise ValueError("figure component proposal is inconsistent")
            if component.artifact_kind is FigureArtifactKind.EMBEDDED_IMAGE:
                artifact = artifact_by_id.get(
                    component.embedded_artifact_id or ""
                )
                if (
                    artifact is None
                    or component.source_block_ids != (artifact.source_block_id,)
                    or component.source_spans != artifact.source_spans
                    or component.source_bounding_box
                    != artifact.source_bounding_box
                ):
                    raise ValueError(
                        "embedded figure component is inconsistent"
                    )
            else:
                drawings = tuple(
                    drawing_by_id[item]
                    for item in component.drawing_evidence_ids
                )
                if component.source_spans != tuple(
                    drawing.source_span for drawing in drawings
                ):
                    raise ValueError(
                        "drawing component source spans are inconsistent"
                    )
                if component.source_bounding_box != _union_boxes(
                    tuple(drawing.source_bounding_box for drawing in drawings)
                ):
                    raise ValueError(
                        "drawing component bounds are inconsistent"
                    )
                validate_component_render(
                    component, result.detection_input.document
                )
        component_id_set = {item.component_id for item in candidate.components}
        caption_associations = tuple(
            association
            for association in candidate.associations
            if association.role is FigureAssociationRole.CAPTION
        )
        if len(caption_associations) > 1:
            raise ValueError("figure candidate has multiple captions")
        expected_label = (
            _source_label(caption_associations[0].text)
            if caption_associations
            else None
        )
        if candidate.source_label != expected_label:
            raise ValueError("figure candidate source label is inconsistent")
        expected_confidence = min(
            component.confidence for component in candidate.components
        )
        if caption_associations:
            expected_confidence = min(1.0, expected_confidence + 0.08)
        else:
            expected_confidence = max(0.0, expected_confidence - 0.25)
        expected_warning_codes: list[str] = []
        if not caption_associations:
            expected_warning_codes.append("figure.caption_missing")
        if expected_confidence < configuration.proposed_confidence_threshold:
            expected_warning_codes.append("figure.low_confidence")
        expected_status = (
            FigureEvidenceStatus.AMBIGUOUS
            if expected_warning_codes
            else FigureEvidenceStatus.PROPOSED
        )
        if (
            candidate.confidence != expected_confidence
            or candidate.evidence_status is not expected_status
            or candidate.evidence
            != (
                ("component_count", str(len(candidate.components))),
                (
                    "caption_present",
                    str(bool(caption_associations)).lower(),
                ),
            )
            or [warning.code for warning in linked_warnings]
            != expected_warning_codes
        ):
            raise ValueError("figure candidate proposal is inconsistent")
        if len({item.block_id for item in candidate.associations}) != len(
            candidate.associations
        ):
            raise ValueError("figure association blocks must be unique")
        for association in candidate.associations:
            block = block_by_id.get(association.block_id)
            if (
                block is None
                or block.text != association.text
                or block.source_spans != association.source_spans
                or association.page_index != candidate.page_index
                or (
                    association.component_id is not None
                    and association.component_id not in component_id_set
                )
            ):
                raise ValueError(
                    "figure association source evidence is inconsistent"
                )
            if association.role is FigureAssociationRole.CAPTION:
                if (
                    association.component_id is not None
                    or _FIGURE_CAPTION.match(association.text) is None
                    or len(association.evidence) != 2
                    or association.evidence[0]
                    != (
                        "method",
                        "explicit_figure_prefix_and_geometry",
                    )
                    or association.evidence[1][0] != "distance_points"
                ):
                    raise ValueError(
                        "figure caption association is inconsistent"
                    )
                caption_box = _block_box(block)
                exact_distance = min(
                    _axis_gap(
                        component.source_bounding_box[1],
                        component.source_bounding_box[3],
                        caption_box[1],
                        caption_box[3],
                    )
                    + _axis_gap(
                        component.source_bounding_box[0],
                        component.source_bounding_box[2],
                        caption_box[0],
                        caption_box[2],
                    )
                    * 0.5
                    for component in candidate.components
                )
                expected_distance_text = _decimal(exact_distance)
                try:
                    distance = float(association.evidence[1][1])
                except ValueError as error:
                    raise ValueError(
                        "figure caption distance is inconsistent"
                    ) from error
                if (
                    association.evidence[1][1] != expected_distance_text
                    or not 0.0
                    <= distance
                    <= configuration.association_distance_points
                    or association.confidence
                    != max(0.70, 1.0 - distance / 720.0)
                ):
                    raise ValueError(
                        "figure caption confidence is inconsistent"
                    )
            elif association.role is FigureAssociationRole.SUBFIGURE_LABEL:
                if (
                    association.component_id is None
                    or _SUBFIGURE_LABEL.match(association.text) is None
                    or association.confidence != 0.88
                    or association.evidence
                    != (("method", "source_text_and_component_geometry"),)
                    or not _near_box(
                        _block_box(block),
                        next(
                            component.source_bounding_box
                            for component in candidate.components
                            if component.component_id
                            == association.component_id
                        ),
                        configuration.association_distance_points / 2.0,
                    )
                ):
                    raise ValueError(
                        "subfigure-label association is inconsistent"
                    )
            elif (
                association.component_id is None
                or _LEGEND.match(association.text) is None
                or association.confidence != 0.76
                or association.evidence
                != (("method", "source_text_and_component_geometry"),)
                or not _near_box(
                    _block_box(block),
                    next(
                        component.source_bounding_box
                        for component in candidate.components
                        if component.component_id == association.component_id
                    ),
                    configuration.association_distance_points / 4.0,
                )
            ):
                raise ValueError("figure legend association is inconsistent")
        total_components += len(candidate.components)
        total_associations += len(candidate.associations)
    if total_components > configuration.max_components:
        raise FigureDetectionLimitError("components exceed max_components")
    if total_associations > configuration.max_associations:
        raise FigureDetectionLimitError("associations exceed max_associations")
    validate_retained_size(result, configuration.max_result_bytes)


def validate_component_render(
    component: FigureComponent,
    document: ExtractedDocument,
) -> None:
    region = component.rendered_region
    if region is None:
        raise ValueError("drawing component lacks rendered evidence")
    page = document.pages[component.page_index]
    if (
        region.source_id != document.source.source_id
        or region.source_blob_id != document.source.blob_id
        or region.source_content_hash != document.source.content_hash
        or region.page_index != component.page_index
        or region.coordinate_system != page.coordinate_system
        or region.page_rotation_degrees != page.rotation_degrees
        or region.selection_was_full_page
    ):
        raise ValueError("drawing render provenance is inconsistent")
    rx0, ry0, rx1, ry1 = region.source_bounding_box
    x0, y0, x1, y1 = component.source_bounding_box
    if rx0 > x0 or ry0 > y0 or rx1 < x1 or ry1 < y1:
        raise ValueError("drawing render does not contain component bounds")


def validate_rendered_aggregate(
    regions: tuple[RenderedRegion, ...],
    configuration: FigureDetectionConfiguration,
) -> None:
    png_bytes = sum(region.byte_length for region in regions)
    pixels = sum(
        region.width_pixels * region.height_pixels for region in regions
    )
    if png_bytes > configuration.max_total_rendered_png_bytes:
        raise FigureDetectionLimitError(
            "rendered PNGs exceed max_total_rendered_png_bytes"
        )
    if pixels > configuration.max_total_rendered_pixels:
        raise FigureDetectionLimitError(
            "rendered regions exceed max_total_rendered_pixels"
        )


def validate_retained_size(value: object, limit: int) -> None:
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
                if field.name in (
                    "content",
                    "mask_content",
                ) and item.__class__.__name__ in (
                    "RenderedRegion",
                    "EmbeddedFigureArtifact",
                ):
                    continue
                stack.append(getattr(item, field.name))
        else:
            raise TypeError("figure result contains unsupported evidence")
        if total > limit:
            raise FigureDetectionLimitError(
                "figure detection result exceeds max_result_bytes"
            )
