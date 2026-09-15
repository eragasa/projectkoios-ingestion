from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from typing import Any, BinaryIO

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedPage,
    ExtractionResult,
    IngestionManifest,
    IngestionStatus,
    IngestionWarning,
    SourceDocument,
    SourceSpan,
    TableOfContentsEntry,
    WarningSeverity,
)

PYMUPDF_COORDINATE_SYSTEM = "pymupdf_unrotated_cropbox_points_top_left"


class PdfDependencyUnavailableError(RuntimeError):
    """Raised when the optional PyMuPDF adapter dependency is absent."""


class PyMuPdfExtractor:
    """Deterministic cold PDF extraction through a lazy optional adapter."""

    name = "pymupdf"
    version = "1"

    def __init__(self, *, low_text_character_threshold: int = 40) -> None:
        if low_text_character_threshold < 0:
            raise ValueError("low-text threshold must be non-negative")
        self.low_text_character_threshold = low_text_character_threshold

    def extract(
        self,
        source: SourceDocument,
        content: BinaryIO,
    ) -> ExtractionResult:
        if source.media_type != "application/pdf":
            raise ValueError("PyMuPdfExtractor requires application/pdf")
        try:
            import pymupdf
        except ImportError as error:  # pragma: no cover - environment dependent
            raise PdfDependencyUnavailableError(
                "PDF extraction requires the 'pdf' project extra"
            ) from error

        payload = content.read()
        self._validate_source(source, payload)
        started = datetime.now(UTC).isoformat()
        document_handle = pymupdf.open(stream=payload, filetype="pdf")
        try:
            if document_handle.needs_pass:
                raise ValueError("encrypted PDF requires a password")
            pages: list[ExtractedPage] = []
            warnings: list[IngestionWarning] = []
            for page_index in range(document_handle.page_count):
                page: Any = document_handle.load_page(page_index)
                extracted_page, page_warnings = self._extract_page(
                    source,
                    page,
                    page_index,
                )
                pages.append(extracted_page)
                warnings.extend(page_warnings)
            metadata = tuple(
                sorted(
                    (str(key), str(value))
                    for key, value in (document_handle.metadata or {}).items()
                    if value not in (None, "")
                )
            )
            table_of_contents = self._extract_table_of_contents(
                source,
                document_handle,
                tuple(pages),
            )
        finally:
            document_handle.close()

        extracted = ExtractedDocument.create(
            source=source,
            pages=tuple(pages),
            metadata=metadata,
            table_of_contents=table_of_contents,
            warning_ids=tuple(warning.warning_id for warning in warnings),
        )
        object_ids = (
            (extracted.document_id,)
            + tuple(block.block_id for page in pages for block in page.blocks)
            + tuple(entry.entry_id for entry in table_of_contents)
        )
        configuration_digest = stable_id(
            "configuration",
            {"low_text_character_threshold": self.low_text_character_threshold},
        )
        manifest = IngestionManifest.create(
            source=source,
            extractor_name=self.name,
            extractor_version=(
                f"{self.version}+pymupdf.{self._backend_version(pymupdf)}"
            ),
            configuration_digest=configuration_digest,
            object_ids=object_ids,
            warning_ids=tuple(warning.warning_id for warning in warnings),
            status=IngestionStatus.COMPLETED,
            started_at=started,
            completed_at=datetime.now(UTC).isoformat(),
        )
        return ExtractionResult(
            document=extracted,
            manifest=manifest,
            warnings=tuple(warnings),
        )

    def _extract_page(
        self,
        source: SourceDocument,
        page: Any,
        page_index: int,
    ) -> tuple[ExtractedPage, tuple[IngestionWarning, ...]]:
        # PyMuPDF's sorting is a reading-order hypothesis. Keep its native
        # source block sequence as cold evidence and warn about ambiguous
        # layout.
        raw = page.get_text("dict", sort=False)
        blocks: list[ExtractedBlock] = []
        text_character_count = 0
        text_boxes: list[tuple[float, float, float, float]] = []
        for ordinal, raw_block in enumerate(raw.get("blocks", [])):
            source_object_id = f"page:{page_index}:block:{ordinal}"
            box = tuple(float(item) for item in raw_block.get("bbox", ()))
            bounding_box = box if len(box) == 4 else None
            span = SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=page_index,
                printed_page_label=self._page_label(page),
                source_object_id=source_object_id,
                bounding_box=bounding_box,
            )
            if raw_block.get("type") == 0:
                text = self._block_text(raw_block)
                if not text:
                    continue
                text_character_count += len(text.strip())
                if bounding_box is not None:
                    text_boxes.append(bounding_box)
                blocks.append(
                    ExtractedBlock.create(
                        kind="text",
                        source_spans=(span,),
                        extraction_method="pymupdf-text-dict",
                        confidence=1.0,
                        text=text,
                    )
                )
            elif raw_block.get("type") == 1:
                image = bytes(raw_block.get("image", b""))
                mask_value = raw_block.get("mask")
                mask = bytes(mask_value) if mask_value is not None else None
                asset_hash = hashlib.sha256(image).hexdigest()
                mask_hash = (
                    hashlib.sha256(mask).hexdigest()
                    if mask is not None
                    else None
                )
                blocks.append(
                    ExtractedBlock.create(
                        kind="image",
                        source_spans=(span,),
                        extraction_method="pymupdf-image-reference",
                        confidence=1.0,
                        asset_id=f"asset:sha256:{asset_hash}",
                        asset_media_type=self._image_media_type(raw_block),
                        asset_mask_id=(
                            f"asset:sha256:{mask_hash}"
                            if mask_hash is not None
                            else None
                        ),
                        asset_mask_media_type=(
                            self._detect_media_type(mask)
                            if mask is not None
                            else None
                        ),
                    )
                )

        warnings: list[IngestionWarning] = []
        if text_character_count < self.low_text_character_threshold:
            warnings.append(
                IngestionWarning.create(
                    code="pdf.low_text_density",
                    severity=WarningSeverity.WARNING,
                    message=(
                        "Page has little extractable text and may require OCR"
                    ),
                    source_spans=(
                        SourceSpan(
                            source_id=source.source_id,
                            source_blob_id=source.blob_id,
                            page_index=page_index,
                            printed_page_label=self._page_label(page),
                        ),
                    ),
                    evidence=(("character_count", str(text_character_count)),),
                    suggested_recovery=(
                        "Inspect the rendered page and request bounded OCR"
                    ),
                )
            )
        column_overlap_pairs = self._multicolumn_overlap_pairs(text_boxes)
        if column_overlap_pairs:
            warnings.append(
                IngestionWarning.create(
                    code="pdf.reading_order_uncertain",
                    severity=WarningSeverity.INFO,
                    message=(
                        "Multiple text columns may make reading order "
                        "uncertain; blocks remain in extractor-native order"
                    ),
                    source_spans=(
                        SourceSpan(
                            source_id=source.source_id,
                            source_blob_id=source.blob_id,
                            page_index=page_index,
                            printed_page_label=self._page_label(page),
                        ),
                    ),
                    evidence=(
                        ("block_order", "extractor_native"),
                        (
                            "separated_vertical_overlap_pairs",
                            str(column_overlap_pairs),
                        ),
                    ),
                    suggested_recovery=(
                        "Proofread block order against the rendered page"
                    ),
                )
            )
        warning_ids = tuple(warning.warning_id for warning in warnings)
        # get_text() and outline destinations use the unrotated cropbox
        # coordinate space, whereas page.rect dimensions rotate with the page.
        page_width = float(page.cropbox.width)
        page_height = float(page.cropbox.height)
        quality = min(1.0, text_character_count / 1000)
        return (
            ExtractedPage(
                page_index=page_index,
                width=page_width,
                height=page_height,
                blocks=tuple(blocks),
                printed_page_label=self._page_label(page),
                extraction_quality=quality,
                warning_ids=warning_ids,
                coordinate_system=PYMUPDF_COORDINATE_SYSTEM,
            ),
            tuple(warnings),
        )

    @staticmethod
    def _block_text(block: dict[str, object]) -> str:
        lines: list[str] = []
        raw_lines = block.get("lines", [])
        if not isinstance(raw_lines, list):
            return ""
        for line in raw_lines:
            if not isinstance(line, dict):
                continue
            spans = line.get("spans", [])
            if not isinstance(spans, list):
                continue
            text = "".join(
                str(span.get("text", ""))
                for span in spans
                if isinstance(span, dict)
            ).rstrip()
            if text:
                lines.append(text)
        return "\n".join(lines)

    @staticmethod
    def _image_media_type(raw_block: dict[str, object]) -> str:
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

    @staticmethod
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

    @staticmethod
    def _page_label(page: Any) -> str | None:
        label = str(page.get_label() or "").strip()
        return label or None

    @staticmethod
    def _multicolumn_overlap_pairs(
        boxes: list[tuple[float, float, float, float]],
    ) -> int:
        count = 0
        for first_index, first in enumerate(boxes):
            for second in boxes[first_index + 1 :]:
                vertical_overlap = min(first[3], second[3]) - max(
                    first[1], second[1]
                )
                separated = first[2] < second[0] or second[2] < first[0]
                if vertical_overlap > 20 and separated:
                    count += 1
        return count

    @staticmethod
    def _backend_version(pymupdf: Any) -> str:
        version = str(getattr(pymupdf, "__version__", "")).strip()
        if not version:
            raise RuntimeError("PyMuPDF does not expose its backend version")
        return version

    def _extract_table_of_contents(
        self,
        source: SourceDocument,
        document: Any,
        pages: tuple[ExtractedPage, ...],
    ) -> tuple[TableOfContentsEntry, ...]:
        entries: list[TableOfContentsEntry] = []
        for raw_entry in document.get_toc(simple=False):
            if not isinstance(raw_entry, list) or len(raw_entry) < 3:
                continue
            level = int(raw_entry[0])
            title = str(raw_entry[1]).strip()
            page_number = int(raw_entry[2])
            details = (
                raw_entry[3]
                if len(raw_entry) > 3 and isinstance(raw_entry[3], dict)
                else {}
            )
            xref = details.get("xref")
            source_object_id = (
                f"pdf-outline-xref:{xref}"
                if isinstance(xref, int) and xref > 0
                else None
            )
            destination = None
            page_index = page_number - 1
            if 0 <= page_index < len(pages):
                point = details.get("to")
                bounding_box = None
                if (
                    point is not None
                    and hasattr(point, "x")
                    and hasattr(point, "y")
                ):
                    x = float(point.x)
                    y = float(point.y)
                    if math.isfinite(x) and math.isfinite(y):
                        bounding_box = (x, y, x, y)
                destination = SourceSpan(
                    source_id=source.source_id,
                    source_blob_id=source.blob_id,
                    page_index=page_index,
                    printed_page_label=pages[page_index].printed_page_label,
                    source_object_id=source_object_id,
                    bounding_box=bounding_box,
                )
            entries.append(
                TableOfContentsEntry.create(
                    source=source,
                    level=level,
                    title=title,
                    destination=destination,
                    source_object_id=source_object_id,
                )
            )
        return tuple(entries)

    @staticmethod
    def _validate_source(source: SourceDocument, payload: bytes) -> None:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != source.content_hash or len(payload) != source.byte_length:
            raise ValueError("source bytes do not agree with SourceDocument")
