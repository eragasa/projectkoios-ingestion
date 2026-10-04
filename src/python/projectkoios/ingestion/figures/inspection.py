"""PyMuPDF-backed bounded figure evidence inspection."""

from __future__ import annotations

import hashlib
from typing import Any, BinaryIO, cast

from projectkoios.ingestion.figures.contracts import (
    FIGURE_INSPECTOR_VERSION,
    EmbeddedFigureArtifact,
    FigureDetectionConfiguration,
    FigureDetectionLimitError,
    FigureDrawingEvidence,
    FigureInspector,
    FigurePageEvidence,
    _box_has_area,
    _box_is_ordered,
    _box_within_page,
    _optional_block_box,
    _positive_integer,
    _validated_box,
    _validated_extent_box,
)
from projectkoios.ingestion.models import (
    ExtractedDocument,
    ExtractedPage,
    SourceDocument,
)


class _PyMuPdfFigureInspector:
    """Lazily retain exact embedded bytes and bounded drawing locators."""

    name = "pymupdf-figure-inspector"
    version = FIGURE_INSPECTOR_VERSION

    @staticmethod
    def inspect(
        inspector: FigureInspector,
        document: ExtractedDocument,
        content: BinaryIO,
        configuration: FigureDetectionConfiguration,
    ) -> tuple[FigurePageEvidence, ...]:
        payload = _read_exact_payload(document.source, content, configuration)
        try:
            import pymupdf
        except ImportError as error:
            from projectkoios.ingestion.pdf.adapters.errors import (
                PdfDependencyUnavailableError,
            )

            raise PdfDependencyUnavailableError(
                "PDF figure inspection requires the optional PyMuPDF dependency"
            ) from error
        backend_name = "PyMuPDF"
        backend_version = str(getattr(pymupdf, "VersionBind", "")).strip()
        if not backend_version:
            raise RuntimeError("PyMuPDF does not expose its backend version")
        pdf = pymupdf.open(  # type: ignore[no-untyped-call]
            stream=payload, filetype="pdf"
        )
        try:
            if len(pdf) != len(document.pages):
                raise ValueError(
                    "PDF page count does not match extracted document"
                )
            results: list[FigurePageEvidence] = []
            total_assets = 0
            total_asset_bytes = 0
            total_drawings = 0
            for offset, extracted_page in enumerate(document.pages):
                page = pdf[offset]
                _verify_page_geometry(page, extracted_page)
                raw = page.get_text(  # type: ignore[no-untyped-call]
                    "dict", sort=False
                )
                raw_blocks = raw.get("blocks", ())
                if len(raw_blocks) > configuration.max_input_blocks:
                    raise FigureDetectionLimitError(
                        "raw PDF blocks exceed max_input_blocks"
                    )
                extracted_by_object = {
                    span.source_object_id: block
                    for block in extracted_page.blocks
                    for span in block.source_spans
                    if span.source_object_id is not None
                }
                artifacts: list[EmbeddedFigureArtifact] = []
                for ordinal, raw_block in enumerate(raw_blocks):
                    if raw_block.get("type") != 1:
                        continue
                    object_id = (
                        f"page:{extracted_page.page_index}:block:{ordinal}"
                    )
                    block = extracted_by_object.get(object_id)
                    if block is None:
                        raise ValueError(
                            "PDF image block is absent from extraction"
                        )
                    image = bytes(raw_block.get("image", b""))
                    mask_value = raw_block.get("mask")
                    mask = bytes(mask_value) if mask_value is not None else None
                    image_hash = hashlib.sha256(image).hexdigest()
                    if block.asset_id != f"asset:sha256:{image_hash}":
                        raise ValueError(
                            "PDF image content differs from raw extraction"
                        )
                    mask_hash = (
                        hashlib.sha256(mask).hexdigest()
                        if mask is not None
                        else None
                    )
                    expected_mask_id = (
                        f"asset:sha256:{mask_hash}"
                        if mask_hash is not None
                        else None
                    )
                    if block.asset_mask_id != expected_mask_id:
                        raise ValueError(
                            "PDF image mask differs from raw extraction"
                        )
                    if block.asset_media_type != _raw_image_media_type(
                        raw_block
                    ):
                        raise ValueError(
                            "PDF image media type differs from raw extraction"
                        )
                    expected_mask_media = (
                        _detect_media_type(mask) if mask is not None else None
                    )
                    if block.asset_mask_media_type != expected_mask_media:
                        raise ValueError(
                            "PDF image mask type differs from raw extraction"
                        )
                    width_pixels = raw_block.get("width", 0)
                    height_pixels = raw_block.get("height", 0)
                    _positive_integer("artifact pixel width", width_pixels)
                    _positive_integer("artifact pixel height", height_pixels)
                    if len(image) > configuration.max_embedded_asset_bytes or (
                        mask is not None
                        and len(mask) > configuration.max_embedded_asset_bytes
                    ):
                        raise FigureDetectionLimitError(
                            "embedded asset exceeds max_embedded_asset_bytes"
                        )
                    total_asset_bytes += len(image) + (len(mask) if mask else 0)
                    if (
                        total_asset_bytes
                        > configuration.max_total_embedded_bytes
                    ):
                        raise FigureDetectionLimitError(
                            "embedded assets exceed max_total_embedded_bytes"
                        )
                    total_assets += 1
                    if total_assets > configuration.max_embedded_assets:
                        raise FigureDetectionLimitError(
                            "embedded assets exceed max_embedded_assets"
                        )
                    try:
                        raw_box = tuple(
                            float(value) for value in raw_block.get("bbox", ())
                        )
                    except TypeError, ValueError, OverflowError:
                        raw_box = ()
                    block_box = _optional_block_box(block)
                    if block_box is None:
                        raw_geometry_is_valid = (
                            len(raw_box) == 4
                            and _box_has_area(raw_box)
                            and all(value >= 0.0 for value in raw_box)
                            and _box_within_page(
                                cast(
                                    tuple[float, float, float, float], raw_box
                                ),
                                extracted_page,
                            )
                        )
                        if not block.warning_ids or raw_geometry_is_valid:
                            raise ValueError(
                                "unlocated PDF image differs from raw "
                                "extraction"
                            )
                        continue
                    if (
                        len(raw_box) != 4
                        or not _box_has_area(raw_box)
                        or _validated_box(raw_box) != block_box
                    ):
                        raise ValueError(
                            "PDF image geometry differs from raw extraction"
                        )
                    artifacts.append(
                        EmbeddedFigureArtifact.create(
                            source=document.source,
                            page_index=extracted_page.page_index,
                            block=block,
                            content=image,
                            mask_content=mask,
                            width_pixels=cast(int, width_pixels),
                            height_pixels=cast(int, height_pixels),
                            processor_name=inspector.name,
                            processor_version=inspector.version,
                            backend_name=backend_name,
                            backend_version=backend_version,
                        )
                    )
                expected_image_ids = tuple(
                    block.block_id
                    for block in extracted_page.blocks
                    if block.kind == "image"
                    and _optional_block_box(block) is not None
                )
                if (
                    tuple(item.source_block_id for item in artifacts)
                    != expected_image_ids
                ):
                    raise ValueError(
                        "embedded artifact extraction is incomplete"
                    )
                raw_drawings = page.get_drawings()
                if (
                    len(raw_drawings)
                    > configuration.max_backend_drawings_per_page
                ):
                    raise FigureDetectionLimitError(
                        "backend drawings exceed their per-page limit"
                    )
                backend_item_count = sum(
                    len(drawing.get("items", ())) for drawing in raw_drawings
                )
                if (
                    backend_item_count
                    > configuration.max_backend_drawing_items_per_page
                ):
                    raise FigureDetectionLimitError(
                        "backend drawing items exceed their per-page limit"
                    )
                retain_stroked_only = (
                    len(raw_drawings) > configuration.max_drawings_per_page
                )
                drawings: list[FigureDrawingEvidence] = []
                ignored = 0
                item_count = 0
                for drawing_index, drawing in enumerate(raw_drawings):
                    items = drawing.get("items", ())
                    has_stroke = drawing.get("color") is not None
                    if retain_stroked_only and not has_stroke:
                        ignored += 1
                        continue
                    item_count += len(items)
                    if item_count > configuration.max_drawing_items_per_page:
                        raise FigureDetectionLimitError(
                            "retained drawing items exceed their per-page limit"
                        )
                    box_value = tuple(
                        float(value) for value in drawing.get("rect", ())
                    )
                    if len(box_value) != 4 or not _box_is_ordered(box_value):
                        ignored += 1
                        continue
                    box = _validated_extent_box(box_value)
                    if not _box_within_page(box, extracted_page):
                        ignored += 1
                        continue
                    if not items:
                        ignored += 1
                        continue
                    drawings.append(
                        FigureDrawingEvidence.create(
                            source=document.source,
                            page_index=extracted_page.page_index,
                            printed_page_label=extracted_page.printed_page_label,
                            source_bounding_box=box,
                            source_object_id=(
                                f"page:{extracted_page.page_index}:"
                                f"drawing:{drawing_index}"
                            ),
                            item_count=len(items),
                            has_stroke=has_stroke,
                            has_fill=drawing.get("fill") is not None,
                        )
                    )
                    if len(drawings) > configuration.max_drawings_per_page:
                        raise FigureDetectionLimitError(
                            "retained drawings exceed their per-page limit"
                        )
                    total_drawings += 1
                    if total_drawings > configuration.max_total_drawings:
                        raise FigureDetectionLimitError(
                            "drawings exceed max_total_drawings"
                        )
                results.append(
                    FigurePageEvidence.create(
                        source=document.source,
                        page=extracted_page,
                        embedded_artifacts=tuple(artifacts),
                        drawings=tuple(drawings),
                        ignored_drawing_count=ignored,
                        processor_name=inspector.name,
                        processor_version=inspector.version,
                        backend_name=backend_name,
                        backend_version=backend_version,
                    )
                )
            return tuple(results)
        finally:
            pdf.close()  # type: ignore[no-untyped-call]


def _raw_image_media_type(raw_block: dict[str, object]) -> str:
    extension = str(raw_block.get("ext", "")).strip().lower()
    return {
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "jpx": "image/jp2",
        "png": "image/png",
        "tif": "image/tiff",
        "tiff": "image/tiff",
    }.get(
        extension,
        f"image/{extension}" if extension else "application/octet-stream",
    )


def _detect_media_type(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if payload.startswith(b"\x00\x00\x00\x0cjP  \r\n\x87\n"):
        return "image/jp2"
    return "application/octet-stream"


def _verify_page_geometry(page: Any, extracted_page: ExtractedPage) -> None:
    if (
        float(page.cropbox.width) != extracted_page.width
        or float(page.cropbox.height) != extracted_page.height
        or int(page.rotation) != extracted_page.rotation_degrees
    ):
        raise ValueError("PDF page geometry does not match extracted document")


def _read_exact_payload(
    source: SourceDocument,
    content: BinaryIO,
    configuration: FigureDetectionConfiguration,
) -> bytes:
    if source.media_type != "application/pdf":
        raise ValueError("figure detection requires application/pdf")
    if source.byte_length > configuration.max_source_bytes:
        raise FigureDetectionLimitError("source exceeds max_source_bytes")
    payload = content.read(configuration.max_source_bytes + 1)
    if not isinstance(payload, bytes):
        raise TypeError("PDF content stream must return bytes")
    if len(payload) > configuration.max_source_bytes:
        raise FigureDetectionLimitError("source exceeds max_source_bytes")
    if len(payload) != source.byte_length:
        raise ValueError("PDF content length does not match source identity")
    if hashlib.sha256(payload).hexdigest() != source.content_hash:
        raise ValueError("PDF content hash does not match source identity")
    return payload


def inspect_pdf_figures(
    inspector: FigureInspector,
    document: ExtractedDocument,
    content: BinaryIO,
    configuration: FigureDetectionConfiguration,
) -> tuple[FigurePageEvidence, ...]:
    """Inspect exact PDF bytes using the public inspector identity."""
    return _PyMuPdfFigureInspector.inspect(
        inspector, document, content, configuration
    )
