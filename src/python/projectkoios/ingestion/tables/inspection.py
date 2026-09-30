"""PyMuPDF-backed bounded table-rule inspection."""

from __future__ import annotations

import hashlib
from typing import BinaryIO, Protocol

from projectkoios.ingestion.models import ExtractedDocument, SourceDocument
from projectkoios.ingestion.tables.contracts import (
    TABLE_RULE_INSPECTOR_VERSION,
    TableDetectionConfiguration,
    TableDetectionLimitError,
    TablePageRuleEvidence,
    TableRuleOrientation,
    TableRuleSegment,
    _nonnegative_float,
    _point_from_backend,
)


class _InspectorIdentity(Protocol):
    name: str
    version: str


class _PyMuPdfTableRuleInspector:
    """Lazily inspect bounded axis-aligned PDF vector line evidence."""

    name = "pymupdf-table-rule-inspector"
    version = TABLE_RULE_INSPECTOR_VERSION

    def inspect(
        self: _InspectorIdentity,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: TableDetectionConfiguration,
    ) -> tuple[TablePageRuleEvidence, ...]:
        payload = _read_exact_payload(document.source, content, configuration)
        try:
            import pymupdf
        except ImportError as error:
            from projectkoios.ingestion.pdf.extractor import (
                PdfDependencyUnavailableError,
            )

            raise PdfDependencyUnavailableError(
                "PDF table-rule inspection requires the optional "
                "PyMuPDF dependency"
            ) from error
        backend_name = "PyMuPDF"
        backend_version = str(getattr(pymupdf, "VersionBind", "unknown"))
        pdf = pymupdf.open(  # type: ignore[no-untyped-call]
            stream=payload, filetype="pdf"
        )
        try:
            if len(pdf) != len(document.pages):
                raise ValueError(
                    "PDF page count does not match extracted document"
                )
            results: list[TablePageRuleEvidence] = []
            total_segments = 0
            for page_offset, extracted_page in enumerate(document.pages):
                pdf_page = pdf[page_offset]
                if (
                    float(pdf_page.cropbox.width) != extracted_page.width
                    or float(pdf_page.cropbox.height) != extracted_page.height
                    or int(pdf_page.rotation) != extracted_page.rotation_degrees
                ):
                    raise ValueError(
                        "PDF page geometry does not match extracted document"
                    )
                drawings = pdf_page.get_drawings()
                if len(drawings) > configuration.max_backend_drawings_per_page:
                    raise TableDetectionLimitError(
                        "backend drawings exceed their per-page limit"
                    )
                backend_item_count = sum(
                    len(drawing.get("items", ())) for drawing in drawings
                )
                if (
                    backend_item_count
                    > configuration.max_backend_drawing_items_per_page
                ):
                    raise TableDetectionLimitError(
                        "backend drawing items exceed their per-page limit"
                    )
                segments: list[TableRuleSegment] = []
                item_count = 0
                ignored_item_count = 0
                retained_drawing_count = 0
                for drawing_index, drawing in enumerate(drawings):
                    items = drawing.get("items", ())
                    has_stroke = drawing.get("color") is not None
                    if not has_stroke:
                        ignored_item_count += len(items)
                        continue
                    retained_drawing_count += 1
                    if (
                        retained_drawing_count
                        > configuration.max_drawings_per_page
                    ):
                        raise TableDetectionLimitError(
                            "stroked drawings exceed their per-page limit"
                        )
                    item_count += len(items)
                    if item_count > configuration.max_drawing_items_per_page:
                        raise TableDetectionLimitError(
                            "stroked drawing items exceed their per-page limit"
                        )
                    width = (
                        _nonnegative_float(
                            "drawing stroke width",
                            drawing.get("width", 0.0),
                        )
                        if has_stroke
                        else 0.0
                    )
                    for item_index, item in enumerate(items):
                        axis_segments = _axis_segments(item)
                        if not axis_segments:
                            ignored_item_count += 1
                        for start, end, suffix in axis_segments:
                            orientation = (
                                TableRuleOrientation.VERTICAL
                                if start[0] == end[0]
                                else TableRuleOrientation.HORIZONTAL
                            )
                            segment = TableRuleSegment.create(
                                source=document.source,
                                page_index=extracted_page.page_index,
                                orientation=orientation,
                                start=start,
                                end=end,
                                stroke_width=width,
                                source_object_id=(
                                    f"page:{extracted_page.page_index}:"
                                    f"drawing:{drawing_index}:item:{item_index}:"
                                    f"segment:{suffix}"
                                ),
                            )
                            segments.append(segment)
                            if len(segments) > (
                                configuration.max_rule_segments_per_page
                            ):
                                raise TableDetectionLimitError(
                                    "rule segments exceed their per-page limit"
                                )
                            total_segments += 1
                            if total_segments > (
                                configuration.max_total_rule_segments
                            ):
                                raise TableDetectionLimitError(
                                    "rule segments exceed their aggregate limit"
                                )
                results.append(
                    TablePageRuleEvidence.create(
                        source=document.source,
                        page_index=extracted_page.page_index,
                        page_width=extracted_page.width,
                        page_height=extracted_page.height,
                        rotation_degrees=extracted_page.rotation_degrees,
                        segments=tuple(segments),
                        ignored_drawing_item_count=ignored_item_count,
                        processor_name=self.name,
                        processor_version=self.version,
                        backend_name=backend_name,
                        backend_version=backend_version,
                    )
                )
            return tuple(results)
        finally:
            pdf.close()  # type: ignore[no-untyped-call]


def _axis_segments(
    item: object,
) -> tuple[tuple[tuple[float, float], tuple[float, float], str], ...]:
    if not isinstance(item, tuple) or not item:
        return ()
    kind = item[0]
    if kind == "l" and len(item) >= 3:
        start = _point_from_backend(item[1])
        end = _point_from_backend(item[2])
        if start != end and (start[0] == end[0] or start[1] == end[1]):
            return ((start, end, "line"),)
        return ()
    if kind == "re" and len(item) >= 2:
        rectangle = item[1]
        try:
            x0 = float(rectangle.x0)
            y0 = float(rectangle.y0)
            x1 = float(rectangle.x1)
            y1 = float(rectangle.y1)
        except AttributeError, TypeError, ValueError:
            return ()
        proposed = (
            ((x0, y0), (x1, y0), "rect-top"),
            ((x1, y0), (x1, y1), "rect-right"),
            ((x1, y1), (x0, y1), "rect-bottom"),
            ((x0, y1), (x0, y0), "rect-left"),
        )
        return tuple(
            segment for segment in proposed if segment[0] != segment[1]
        )
    return ()


def _read_exact_payload(
    source: SourceDocument,
    content: BinaryIO,
    configuration: TableDetectionConfiguration,
) -> bytes:
    if source.byte_length > configuration.max_source_bytes:
        raise TableDetectionLimitError("source exceeds max_source_bytes")
    payload = content.read(configuration.max_source_bytes + 1)
    if not isinstance(payload, bytes):
        raise TypeError("PDF content stream must return bytes")
    if len(payload) > configuration.max_source_bytes:
        raise TableDetectionLimitError("source exceeds max_source_bytes")
    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != source.byte_length or digest != source.content_hash:
        raise ValueError("source bytes do not agree with SourceDocument")
    return payload


def inspect_pdf_table_rules(
    inspector: _InspectorIdentity,
    document: ExtractedDocument,
    content: BinaryIO,
    configuration: TableDetectionConfiguration,
) -> tuple[TablePageRuleEvidence, ...]:
    """Inspect exact PDF bytes using the public inspector identity."""
    return _PyMuPdfTableRuleInspector.inspect(
        inspector, document, content, configuration
    )
