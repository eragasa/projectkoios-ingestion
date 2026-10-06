from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, BinaryIO

from projectkoios.ingestion.cache_identity import build_extraction_cache_key
from projectkoios.ingestion.models import (
    CONTRACT_VERSION,
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
from projectkoios.ingestion.pdf.adapters.errors import (
    PdfDependencyUnavailableError,
)
from projectkoios.ingestion.pdf.extraction.contracts import (
    DEFAULT_MAXIMUM_PDF_PAGES,
    PdfExtractionConfiguration,
    PdfPageLimitError,
)
from projectkoios.ingestion.pdf.extraction.geometry import (
    BlockGeometryActionizer,
    BlockGeometryRequest,
)
from projectkoios.ingestion.pdf.extraction.text import (
    MAXIMUM_BLOCK_TEXT_CHARACTERS,
    MAXIMUM_BLOCK_TEXT_LINES,
    MAXIMUM_BLOCK_TEXT_SPANS,
    BlockTextActionizer,
    BlockTextLimitError,
    BlockTextRequest,
)
from projectkoios.ingestion.pdf.models import PYMUPDF_COORDINATE_SYSTEM
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.storage.extraction.freeze.bounded.extractor import (
    FreezableSourceExtractor,
)


class PyMuPdfExtractor(FreezableSourceExtractor):
    """Deterministic cold PDF extraction through a lazy optional adapter."""

    name = "pymupdf"
    version = "4"
    _block_geometry_actionizer = BlockGeometryActionizer()
    _block_text_actionizer = BlockTextActionizer()

    def __init__(
        self,
        *,
        low_text_character_threshold: int = 40,
        maximum_pages: int = DEFAULT_MAXIMUM_PDF_PAGES,
    ) -> None:
        self.configuration = PdfExtractionConfiguration(
            low_text_character_threshold=low_text_character_threshold,
            maximum_pages=maximum_pages,
        )

    @property
    def low_text_character_threshold(self) -> int:
        return self.configuration.low_text_character_threshold

    @property
    def maximum_pages(self) -> int:
        return self.configuration.maximum_pages

    @property
    def extraction_version(self) -> str:
        try:
            import pymupdf
        except ImportError as error:  # pragma: no cover - environment dependent
            raise PdfDependencyUnavailableError(
                "PDF extraction requires the 'pdf' project extra"
            ) from error
        return self._extractor_version(pymupdf)

    @property
    def configuration_digest(self) -> str:
        return self.configuration.configuration_digest

    def cache_key(self, source: SourceDocument) -> str:
        """Return the key extraction will record for this source and backend."""
        try:
            import pymupdf
        except ImportError as error:  # pragma: no cover - environment dependent
            raise PdfDependencyUnavailableError(
                "PDF extraction requires the 'pdf' project extra"
            ) from error
        return build_extraction_cache_key(
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            extractor_name=self.name,
            extractor_version=self._extractor_version(pymupdf),
            configuration_digest=self.configuration_digest,
            contract_version=CONTRACT_VERSION,
        )

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
            page_count = document_handle.page_count
            if (
                isinstance(page_count, bool)
                or not isinstance(page_count, int)
                or page_count < 0
            ):
                raise ValueError("PDF backend returned an invalid page count")
            if page_count > self.maximum_pages:
                raise PdfPageLimitError(
                    page_count=page_count,
                    maximum_pages=self.maximum_pages,
                )
            pages: list[ExtractedPage] = []
            warnings: list[IngestionWarning] = []
            for page_index in range(page_count):
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
        manifest = IngestionManifest.create(
            source=source,
            extractor_name=self.name,
            extractor_version=self._extractor_version(pymupdf),
            configuration_digest=self.configuration_digest,
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
        # PyMuPDF's sorting is a reading-order hypothesis. Cold extraction
        # retains its native source sequence; layout is a separate derivation.
        raw = page.get_text("dict", sort=False)
        # get_text() uses the unrotated cropbox coordinate space. Preserve
        # content whose backend box escapes that space, but make its geometry
        # unavailable rather than clamping or synthesizing coordinates.
        page_width = float(page.cropbox.width)
        page_height = float(page.cropbox.height)
        blocks: list[ExtractedBlock] = []
        warnings: list[IngestionWarning] = []
        text_character_count = 0
        for ordinal, raw_block in enumerate(raw.get("blocks", [])):
            block_type = raw_block.get("type")
            text: str | None = None
            if block_type == 0:
                text_lines: list[tuple[str, ...]] = []
                span_count = 0
                character_count = 0
                raw_lines = raw_block.get("lines", [])
                if isinstance(raw_lines, list):
                    if len(raw_lines) > MAXIMUM_BLOCK_TEXT_LINES:
                        raise BlockTextLimitError(
                            "block text lines exceed their limit"
                        )
                    for raw_line in raw_lines:
                        if not isinstance(raw_line, dict):
                            continue
                        raw_spans = raw_line.get("spans", [])
                        if not isinstance(raw_spans, list):
                            continue
                        span_count += len(raw_spans)
                        if span_count > MAXIMUM_BLOCK_TEXT_SPANS:
                            raise BlockTextLimitError(
                                "block text spans exceed their limit"
                            )
                        line: list[str] = []
                        for raw_span in raw_spans:
                            if not isinstance(raw_span, dict):
                                continue
                            span_text = str(raw_span.get("text", ""))
                            character_count += len(span_text)
                            if character_count > MAXIMUM_BLOCK_TEXT_CHARACTERS:
                                raise BlockTextLimitError(
                                    "block text characters exceed their limit"
                                )
                            line.append(span_text)
                        text_lines.append(tuple(line))
                text_request = BlockTextRequest.create(lines=tuple(text_lines))
                text = self._block_text_actionizer.action(
                    request=text_request
                ).text
            if block_type not in (0, 1) or (block_type == 0 and not text):
                continue
            source_object_id = f"page:{page_index}:block:{ordinal}"
            raw_bounding_box = raw_block.get("bbox")
            if isinstance(raw_bounding_box, (list, tuple)):
                try:
                    coordinates = tuple(
                        float(item) for item in raw_bounding_box[:5]
                    )
                    geometry_request = BlockGeometryRequest.create(
                        coordinates=coordinates,
                        coordinate_count=len(raw_bounding_box),
                    )
                except TypeError, ValueError, OverflowError:
                    geometry_request = BlockGeometryRequest.create()
            else:
                geometry_request = BlockGeometryRequest.create()
            geometry = self._block_geometry_actionizer.action(
                request=geometry_request
            )
            bounding_box = geometry.bounding_box
            invalid_reason = geometry.invalid_reason
            if bounding_box is not None and (
                bounding_box[2] > page_width or bounding_box[3] > page_height
            ):
                bounding_box = None
                invalid_reason = "outside_page"
            span = SourceSpan(
                source_id=source.source_id,
                source_blob_id=source.blob_id,
                page_index=page_index,
                printed_page_label=self._page_label(page),
                source_object_id=source_object_id,
                bounding_box=bounding_box,
            )
            block_warning_ids: tuple[str, ...] = ()
            if invalid_reason is not None:
                warning = IngestionWarning.create(
                    code="pdf.invalid_block_geometry",
                    severity=WarningSeverity.WARNING,
                    message=(
                        "PDF backend block geometry is invalid; the block was "
                        "preserved without a bounding box"
                    ),
                    object_ids=(source_object_id,),
                    source_spans=(span,),
                    evidence=(
                        ("block_type", "text" if block_type == 0 else "image"),
                        ("geometry_reason", invalid_reason),
                        ("raw_bounding_box", geometry.raw_evidence),
                    ),
                    suggested_recovery=(
                        "Retain the content as unlocated evidence and inspect "
                        "the rendered page when geometry is required"
                    ),
                )
                warnings.append(warning)
                block_warning_ids = (warning.warning_id,)
            if block_type == 0:
                assert text is not None
                text_character_count += len(text.strip())
                blocks.append(
                    ExtractedBlock.create(
                        kind="text",
                        source_spans=(span,),
                        extraction_method="pymupdf-text-dict",
                        confidence=1.0,
                        text=text,
                        warning_ids=block_warning_ids,
                    )
                )
            else:
                image = bytes(raw_block.get("image", b""))
                mask_value = raw_block.get("mask")
                mask = bytes(mask_value) if mask_value is not None else None
                asset_hash = SHA256Fingerprinter.fingerprint(content=image)
                mask_hash = (
                    SHA256Fingerprinter.fingerprint(content=mask)
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
                        warning_ids=block_warning_ids,
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
        warning_ids = tuple(warning.warning_id for warning in warnings)
        # get_text() and outline destinations use the unrotated cropbox
        # coordinate space, whereas page.rect dimensions rotate with the page.
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
                rotation_degrees=int(page.rotation),
            ),
            tuple(warnings),
        )

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

    @classmethod
    def _extractor_version(cls, pymupdf: Any) -> str:
        return f"{cls.version}+pymupdf.{cls._backend_version(pymupdf)}"

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
        digest = SHA256Fingerprinter.fingerprint(content=payload)
        if digest != source.content_hash or len(payload) != source.byte_length:
            raise ValueError("source bytes do not agree with SourceDocument")
