from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from projectkoios.ingestion.identity import sha256_digest, stable_id

CONTRACT_VERSION = "2.0"
BoundingBox = tuple[float, float, float, float]
Metadata = tuple[tuple[str, str], ...]


class WarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IngestionStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    blob_id: str
    media_type: str
    content_hash: str
    hash_algorithm: str
    byte_length: int
    locator: str

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        *,
        source_id: str,
        media_type: str,
        locator: str,
    ) -> SourceDocument:
        digest = sha256_digest(content)
        return cls(
            source_id=source_id,
            blob_id=f"blob:sha256:{digest}",
            media_type=media_type,
            content_hash=digest,
            hash_algorithm="sha256",
            byte_length=len(content),
            locator=locator,
        )

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        if not self.media_type:
            raise ValueError("media_type must be non-empty")
        if not self.locator:
            raise ValueError("locator must be non-empty")
        if self.byte_length < 0:
            raise ValueError("byte_length must be non-negative")
        if self.hash_algorithm != "sha256":
            raise ValueError(
                "only sha256 source hashes are currently supported"
            )
        if len(self.content_hash) != 64:
            raise ValueError("content_hash must be a SHA-256 hex digest")
        try:
            int(self.content_hash, 16)
        except ValueError as error:
            raise ValueError(
                "content_hash must be a SHA-256 hex digest"
            ) from error
        if self.blob_id != f"blob:sha256:{self.content_hash}":
            raise ValueError("blob_id must agree with content_hash")


@dataclass(frozen=True)
class SourceSpan:
    source_id: str
    source_blob_id: str
    page_index: int
    printed_page_label: str | None = None
    source_object_id: str | None = None
    bounding_box: BoundingBox | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        if not self.source_blob_id:
            raise ValueError("source_blob_id must be non-empty")
        if self.page_index < 0:
            raise ValueError("page_index must be non-negative")
        if self.bounding_box is not None:
            x0, y0, x1, y1 = self.bounding_box
            if x1 < x0 or y1 < y0:
                raise ValueError("bounding_box must have ordered coordinates")
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("start_offset and end_offset must be set together")
        if self.start_offset is not None and self.end_offset is not None:
            if self.start_offset < 0 or self.end_offset < self.start_offset:
                raise ValueError(
                    "source offsets must be ordered and non-negative"
                )

    def identity_parts(self) -> tuple[object, ...]:
        """Return source-local evidence, excluding mutable display labels."""
        return (
            self.source_id,
            self.source_blob_id,
            self.page_index,
            self.source_object_id,
            self.bounding_box,
            self.start_offset,
            self.end_offset,
        )


@dataclass(frozen=True)
class IngestionWarning:
    warning_id: str
    code: str
    severity: WarningSeverity
    message: str
    object_ids: tuple[str, ...] = ()
    source_spans: tuple[SourceSpan, ...] = ()
    evidence: Metadata = ()
    suggested_recovery: str | None = None

    @classmethod
    def create(
        cls,
        *,
        code: str,
        severity: WarningSeverity,
        message: str,
        object_ids: tuple[str, ...] = (),
        source_spans: tuple[SourceSpan, ...] = (),
        evidence: Metadata = (),
        suggested_recovery: str | None = None,
    ) -> IngestionWarning:
        warning_id = stable_id(
            "warning",
            code,
            object_ids,
            tuple(span.identity_parts() for span in source_spans),
            evidence,
        )
        return cls(
            warning_id=warning_id,
            code=code,
            severity=severity,
            message=message,
            object_ids=object_ids,
            source_spans=source_spans,
            evidence=evidence,
            suggested_recovery=suggested_recovery,
        )

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("warning code must be non-empty")
        if not self.message:
            raise ValueError("warning message must be non-empty")


@dataclass(frozen=True)
class ExtractedBlock:
    block_id: str
    kind: str
    source_spans: tuple[SourceSpan, ...]
    extraction_method: str
    confidence: float
    text: str | None = None
    asset_id: str | None = None
    warning_ids: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        kind: str,
        source_spans: tuple[SourceSpan, ...],
        extraction_method: str,
        confidence: float,
        text: str | None = None,
        asset_id: str | None = None,
        warning_ids: tuple[str, ...] = (),
    ) -> ExtractedBlock:
        has_source_local_evidence = any(
            span.source_object_id is not None
            or span.bounding_box is not None
            or span.start_offset is not None
            for span in source_spans
        )
        fallback_payload = None
        if not has_source_local_evidence:
            fallback_payload = (text, asset_id)

        block_id = stable_id(
            "block",
            kind,
            tuple(span.identity_parts() for span in source_spans),
            fallback_payload,
        )
        return cls(
            block_id=block_id,
            kind=kind,
            source_spans=source_spans,
            extraction_method=extraction_method,
            confidence=confidence,
            text=text,
            asset_id=asset_id,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("block kind must be non-empty")
        if not self.source_spans:
            raise ValueError("a block must have at least one source span")
        if not self.extraction_method:
            raise ValueError("extraction_method must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.text is None and self.asset_id is None:
            raise ValueError("a block must contain text or an asset reference")


@dataclass(frozen=True)
class ExtractedPage:
    page_index: int
    width: float
    height: float
    blocks: tuple[ExtractedBlock, ...]
    printed_page_label: str | None = None
    extraction_quality: float = 1.0
    warning_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise ValueError("page_index must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("page dimensions must be positive")
        if not 0.0 <= self.extraction_quality <= 1.0:
            raise ValueError("extraction_quality must be between 0 and 1")
        for block in self.blocks:
            if any(
                span.page_index != self.page_index
                for span in block.source_spans
            ):
                raise ValueError(
                    "page blocks must refer to the containing page"
                )


@dataclass(frozen=True)
class ExtractedDocument:
    document_id: str
    source: SourceDocument
    pages: tuple[ExtractedPage, ...]
    metadata: Metadata = ()
    warning_ids: tuple[str, ...] = ()
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        pages: tuple[ExtractedPage, ...],
        metadata: Metadata = (),
        warning_ids: tuple[str, ...] = (),
    ) -> ExtractedDocument:
        return cls(
            document_id=stable_id("document", source.source_id),
            source=source,
            pages=pages,
            metadata=metadata,
            warning_ids=warning_ids,
        )

    def __post_init__(self) -> None:
        page_indices = tuple(page.page_index for page in self.pages)
        if page_indices != tuple(sorted(set(page_indices))):
            raise ValueError("pages must have unique ascending page indices")
        for page in self.pages:
            for block in page.blocks:
                if any(
                    span.source_id != self.source.source_id
                    or span.source_blob_id != self.source.blob_id
                    for span in block.source_spans
                ):
                    raise ValueError(
                        "block spans must refer to the exact document source"
                    )


@dataclass(frozen=True)
class IngestionManifest:
    manifest_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    extractor_name: str
    extractor_version: str
    configuration_digest: str
    object_ids: tuple[str, ...]
    warning_ids: tuple[str, ...]
    cache_key: str
    status: IngestionStatus
    started_at: str
    completed_at: str | None = None
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source: SourceDocument,
        extractor_name: str,
        extractor_version: str,
        configuration_digest: str,
        object_ids: tuple[str, ...],
        warning_ids: tuple[str, ...],
        status: IngestionStatus,
        started_at: str,
        completed_at: str | None = None,
    ) -> IngestionManifest:
        cache_key = stable_id(
            "extraction-cache",
            source.source_id,
            source.blob_id,
            extractor_name,
            extractor_version,
            configuration_digest,
        )
        manifest_id = stable_id(
            "manifest",
            cache_key,
            object_ids,
            warning_ids,
            status,
        )
        return cls(
            manifest_id=manifest_id,
            source_id=source.source_id,
            source_blob_id=source.blob_id,
            source_content_hash=source.content_hash,
            extractor_name=extractor_name,
            extractor_version=extractor_version,
            configuration_digest=configuration_digest,
            object_ids=object_ids,
            warning_ids=warning_ids,
            cache_key=cache_key,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
        )

    def __post_init__(self) -> None:
        if not self.extractor_name or not self.extractor_version:
            raise ValueError("extractor identity must be complete")
        if not self.configuration_digest:
            raise ValueError("configuration_digest must be non-empty")
        if not self.started_at:
            raise ValueError("started_at must be non-empty")


@dataclass(frozen=True)
class ExtractionResult:
    document: ExtractedDocument
    manifest: IngestionManifest
    warnings: tuple[IngestionWarning, ...] = ()

    def __post_init__(self) -> None:
        if self.manifest.source_id != self.document.source.source_id:
            raise ValueError("manifest and document must have the same source")
        if self.manifest.source_blob_id != self.document.source.blob_id:
            raise ValueError(
                "manifest and document must have the same source blob"
            )
        if (
            self.manifest.source_content_hash
            != self.document.source.content_hash
        ):
            raise ValueError("manifest and document source hashes must match")
        if self.document.document_id not in self.manifest.object_ids:
            raise ValueError("manifest must include the document object ID")
        warning_ids = tuple(warning.warning_id for warning in self.warnings)
        if warning_ids != self.manifest.warning_ids:
            raise ValueError("manifest warning IDs must match result warnings")
