from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath

from projectkoios.ingestion.cache import deserialize_extraction_result
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import (
    ExtractedPage,
    ExtractionResult,
    IngestionStatus,
    Metadata,
    SourceDocument,
)
from projectkoios.ingestion.pdf.adapters.pymupdf.extraction import (
    PyMuPdfExtractor,
)
from projectkoios.ingestion.pdf.extraction.contracts import (
    PdfExtractionConfiguration,
)
from projectkoios.ingestion.serialization import serialize_contract

PDF_EXTRACTION_ARTIFACT_CONTRACT_VERSION = "1.0"
RAW_EXTRACTION_RELATIVE_PATH = "raw-extraction.json"
RAW_EXTRACTION_MEDIA_TYPE = (
    "application/vnd.projectkoios.ingestion.extraction+json"
)
RAW_PAGE_TEXT_MEDIA_TYPE = "text/plain; charset=utf-8"
RAW_PAGE_DIRECTORY = "raw-pages"
_HARD_MAX_ARTIFACTS = 100_001
_HARD_MAX_RAW_EXTRACTION_BYTES = 64_000_000
_HARD_MAX_PAGE_TEXT_BYTES = 16_000_000
_HARD_MAX_TOTAL_ARTIFACT_BYTES = 256_000_000
_HARD_MAX_RELATIVE_PATH_BYTES = 1_024
_HARD_MAX_IDENTITY_TEXT_BYTES = 4_096


class PdfSourceIntegrityError(ValueError):
    """Raised when exact staged PDF bytes do not match planned identity."""


class PdfExtractionArtifactLimitError(ValueError):
    """Raised when a pure extraction artifact exceeds a configured bound."""


class PdfExtractionArtifactValidationError(ValueError):
    """Raised when an artifact bundle is noncanonical or inconsistent."""


class PdfExtractionArtifactIncompleteError(
    PdfExtractionArtifactValidationError
):
    """Raised when a replay artifact tuple has missing or extra members."""


class PdfExtractionArtifactMalformedError(PdfExtractionArtifactValidationError):
    """Raised when replay evidence is malformed or inconsistent."""


@dataclass(frozen=True)
class PdfExtractionArtifactLimits:
    max_artifacts: int = _HARD_MAX_ARTIFACTS
    max_raw_extraction_bytes: int = _HARD_MAX_RAW_EXTRACTION_BYTES
    max_page_text_bytes: int = _HARD_MAX_PAGE_TEXT_BYTES
    max_total_artifact_bytes: int = _HARD_MAX_TOTAL_ARTIFACT_BYTES

    def __post_init__(self) -> None:
        maxima = {
            "max_artifacts": _HARD_MAX_ARTIFACTS,
            "max_raw_extraction_bytes": _HARD_MAX_RAW_EXTRACTION_BYTES,
            "max_page_text_bytes": _HARD_MAX_PAGE_TEXT_BYTES,
            "max_total_artifact_bytes": _HARD_MAX_TOTAL_ARTIFACT_BYTES,
        }
        for name, maximum in maxima.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
                or value > maximum
            ):
                raise ValueError(
                    f"{name} must be a positive integer no greater than "
                    f"{maximum}"
                )
        if self.max_total_artifact_bytes < max(
            self.max_raw_extraction_bytes,
            self.max_page_text_bytes,
        ):
            raise ValueError(
                "max_total_artifact_bytes cannot be smaller than an "
                "individual artifact limit"
            )


@dataclass(frozen=True)
class PdfExtractionArtifactPayload:
    relative_path: str
    media_type: str
    byte_length: int
    content_sha256: str
    content: bytes

    @classmethod
    def create(
        cls,
        *,
        relative_path: str,
        media_type: str,
        content: bytes,
    ) -> PdfExtractionArtifactPayload:
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be immutable bytes")
        return cls(
            relative_path=relative_path,
            media_type=media_type,
            byte_length=len(content),
            content_sha256=hashlib.sha256(content).hexdigest(),
            content=content,
        )

    def __post_init__(self) -> None:
        _validate_relative_path(self.relative_path)
        _bounded_text("media_type", self.media_type, 256)
        if not isinstance(self.content, bytes):
            raise TypeError("artifact content must be immutable bytes")
        if (
            isinstance(self.byte_length, bool)
            or not isinstance(self.byte_length, int)
            or self.byte_length < 0
            or self.byte_length != len(self.content)
        ):
            raise PdfExtractionArtifactValidationError(
                "artifact byte length does not match content"
            )
        if self.byte_length > _HARD_MAX_TOTAL_ARTIFACT_BYTES:
            raise PdfExtractionArtifactLimitError(
                "artifact content exceeds the implementation byte limit"
            )
        digest = hashlib.sha256(self.content).hexdigest()
        if self.content_sha256 != digest:
            raise PdfExtractionArtifactValidationError(
                "artifact content hash does not match content"
            )


@dataclass(frozen=True)
class PdfExtractionTranscriptPage:
    """Exact native extracted text for one physical source page."""

    page_id: str
    page_index: int
    printed_page_label: str | None
    text: str


@dataclass(frozen=True)
class PdfExtractionTranscript:
    """Owner-validated semantic replay of one extraction artifact bundle."""

    bundle_id: str
    source_id: str
    source_blob_id: str
    source_sha256: str
    source_byte_size: int
    media_type: str
    metadata: Metadata
    manifest_id: str
    status: IngestionStatus
    review_status: str
    pages: tuple[PdfExtractionTranscriptPage, ...]


@dataclass(frozen=True)
class PdfExtractionArtifactBundle:
    bundle_id: str
    contract_version: str
    configuration: PdfExtractionConfiguration
    artifact_limits: PdfExtractionArtifactLimits
    result: ExtractionResult
    artifacts: tuple[PdfExtractionArtifactPayload, ...]

    @classmethod
    def create(
        cls,
        *,
        configuration: PdfExtractionConfiguration,
        artifact_limits: PdfExtractionArtifactLimits,
        result: ExtractionResult,
    ) -> PdfExtractionArtifactBundle:
        artifacts = _artifact_payloads(result, artifact_limits)
        bundle_id = _bundle_id(
            configuration=configuration,
            artifact_limits=artifact_limits,
            result=result,
            artifacts=artifacts,
        )
        return cls(
            bundle_id=bundle_id,
            contract_version=PDF_EXTRACTION_ARTIFACT_CONTRACT_VERSION,
            configuration=configuration,
            artifact_limits=artifact_limits,
            result=result,
            artifacts=artifacts,
        )

    def __post_init__(self) -> None:
        if self.contract_version != PDF_EXTRACTION_ARTIFACT_CONTRACT_VERSION:
            raise PdfExtractionArtifactValidationError(
                "unsupported PDF extraction artifact contract version"
            )
        if not isinstance(self.configuration, PdfExtractionConfiguration):
            raise TypeError("configuration must be PdfExtractionConfiguration")
        if not isinstance(self.artifact_limits, PdfExtractionArtifactLimits):
            raise TypeError(
                "artifact_limits must be PdfExtractionArtifactLimits"
            )
        if not isinstance(self.result, ExtractionResult):
            raise TypeError("result must be an ExtractionResult")
        if (
            not isinstance(self.artifacts, tuple)
            or not self.artifacts
            or any(
                not isinstance(item, PdfExtractionArtifactPayload)
                for item in self.artifacts
            )
        ):
            raise PdfExtractionArtifactValidationError(
                "artifacts must be a nonempty immutable payload tuple"
            )
        if len(self.artifacts) > self.artifact_limits.max_artifacts:
            raise PdfExtractionArtifactLimitError(
                "artifact tuple exceeds max_artifacts"
            )
        if sum(item.byte_length for item in self.artifacts) > (
            self.artifact_limits.max_total_artifact_bytes
        ):
            raise PdfExtractionArtifactLimitError(
                "artifact tuple exceeds max_total_artifact_bytes"
            )
        if (
            self.result.manifest.configuration_digest
            != self.configuration.configuration_digest
        ):
            raise PdfExtractionArtifactValidationError(
                "result and extraction configuration disagree"
            )
        if len(self.result.document.pages) > self.configuration.maximum_pages:
            raise PdfExtractionArtifactValidationError(
                "result page count exceeds extraction configuration"
            )
        expected_artifacts = _artifact_payloads(
            self.result, self.artifact_limits
        )
        if self.artifacts != expected_artifacts:
            raise PdfExtractionArtifactValidationError(
                "artifact payloads are not canonical for extraction result"
            )
        expected_id = _bundle_id(
            configuration=self.configuration,
            artifact_limits=self.artifact_limits,
            result=self.result,
            artifacts=self.artifacts,
        )
        if self.bundle_id != expected_id:
            raise PdfExtractionArtifactValidationError(
                "PDF extraction artifact bundle identity mismatch"
            )


def extract_pdf_bytes(
    content: bytes,
    *,
    source_id: str,
    locator: str,
    low_text_character_threshold: int,
    expected_source_sha256: str,
    expected_source_byte_size: int,
    maximum_pages: int,
) -> ExtractionResult:
    """Extract exact immutable PDF bytes without filesystem mutation."""
    source, configuration = prepare_pdf_bytes_extraction(
        content,
        source_id=source_id,
        locator=locator,
        low_text_character_threshold=low_text_character_threshold,
        expected_source_sha256=expected_source_sha256,
        expected_source_byte_size=expected_source_byte_size,
        maximum_pages=maximum_pages,
    )
    return _extract_prepared_pdf(content, source, configuration)


def extract_pdf_bytes_artifacts(
    content: bytes,
    *,
    source_id: str,
    locator: str,
    low_text_character_threshold: int,
    expected_source_sha256: str,
    expected_source_byte_size: int,
    maximum_pages: int,
    artifact_limits: PdfExtractionArtifactLimits | None = None,
) -> PdfExtractionArtifactBundle:
    """Extract exact bytes and build bounded in-memory artifacts."""
    source, configuration = prepare_pdf_bytes_extraction(
        content,
        source_id=source_id,
        locator=locator,
        low_text_character_threshold=low_text_character_threshold,
        expected_source_sha256=expected_source_sha256,
        expected_source_byte_size=expected_source_byte_size,
        maximum_pages=maximum_pages,
    )
    actual_limits = (
        PdfExtractionArtifactLimits()
        if artifact_limits is None
        else artifact_limits
    )
    if not isinstance(actual_limits, PdfExtractionArtifactLimits):
        raise TypeError("artifact_limits must be PdfExtractionArtifactLimits")
    if configuration.maximum_pages + 1 > actual_limits.max_artifacts:
        raise PdfExtractionArtifactLimitError(
            "maximum_pages and max_artifacts are incoherent"
        )
    result = _extract_prepared_pdf(content, source, configuration)
    return PdfExtractionArtifactBundle.create(
        configuration=configuration,
        artifact_limits=actual_limits,
        result=result,
    )


def prepare_pdf_bytes_extraction(
    content: bytes,
    *,
    source_id: str,
    locator: str,
    low_text_character_threshold: int,
    expected_source_sha256: str,
    expected_source_byte_size: int,
    maximum_pages: int,
) -> tuple[SourceDocument, PdfExtractionConfiguration]:
    """Validate staged bytes and return exact source/configuration evidence."""
    if not isinstance(content, bytes):
        raise TypeError("PDF content must be exact immutable bytes")
    _bounded_text("source_id", source_id, _HARD_MAX_IDENTITY_TEXT_BYTES)
    _bounded_text("locator", locator, _HARD_MAX_IDENTITY_TEXT_BYTES)
    expected_digest = _validated_sha256(expected_source_sha256)
    if (
        isinstance(expected_source_byte_size, bool)
        or not isinstance(expected_source_byte_size, int)
        or expected_source_byte_size < 0
    ):
        raise PdfSourceIntegrityError(
            "expected_source_byte_size must be a non-negative integer"
        )
    if len(content) != expected_source_byte_size:
        raise PdfSourceIntegrityError(
            "PDF source size does not match the planned byte size"
        )
    actual_digest = hashlib.sha256(content).hexdigest()
    if actual_digest != expected_digest:
        raise PdfSourceIntegrityError(
            "PDF source hash does not match the planned SHA-256"
        )
    configuration = PdfExtractionConfiguration(
        low_text_character_threshold=low_text_character_threshold,
        maximum_pages=maximum_pages,
    )
    source = SourceDocument.from_bytes(
        content,
        source_id=source_id,
        media_type="application/pdf",
        locator=locator,
    )
    return source, configuration


def build_pdf_extraction_artifacts(
    result: ExtractionResult,
    *,
    configuration: PdfExtractionConfiguration,
    artifact_limits: PdfExtractionArtifactLimits | None = None,
) -> PdfExtractionArtifactBundle:
    """Build canonical bounded byte payloads without filesystem mutation."""
    if not isinstance(result, ExtractionResult):
        raise TypeError("result must be an ExtractionResult")
    if not isinstance(configuration, PdfExtractionConfiguration):
        raise TypeError("configuration must be PdfExtractionConfiguration")
    actual_limits = (
        PdfExtractionArtifactLimits()
        if artifact_limits is None
        else artifact_limits
    )
    if not isinstance(actual_limits, PdfExtractionArtifactLimits):
        raise TypeError("artifact_limits must be PdfExtractionArtifactLimits")
    return PdfExtractionArtifactBundle.create(
        configuration=configuration,
        artifact_limits=actual_limits,
        result=result,
    )


def read_pdf_extraction_transcript(
    artifacts: tuple[PdfExtractionArtifactPayload, ...],
    *,
    expected_bundle_id: str,
    expected_source_sha256: str,
    expected_source_byte_size: int,
    configuration: PdfExtractionConfiguration,
    artifact_limits: PdfExtractionArtifactLimits,
) -> PdfExtractionTranscript:
    """Strictly replay one complete bounded extraction artifact tuple."""
    if not isinstance(configuration, PdfExtractionConfiguration):
        raise TypeError("configuration must be PdfExtractionConfiguration")
    if not isinstance(artifact_limits, PdfExtractionArtifactLimits):
        raise TypeError("artifact_limits must be PdfExtractionArtifactLimits")
    if not isinstance(artifacts, tuple) or not artifacts:
        raise PdfExtractionArtifactIncompleteError(
            "artifacts must be a nonempty immutable payload tuple"
        )
    if len(artifacts) > artifact_limits.max_artifacts:
        raise PdfExtractionArtifactLimitError(
            "artifact tuple exceeds max_artifacts"
        )

    total_bytes = 0
    paths: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, PdfExtractionArtifactPayload):
            raise PdfExtractionArtifactMalformedError(
                "artifacts must contain only PdfExtractionArtifactPayload"
            )
        try:
            PdfExtractionArtifactPayload(
                relative_path=artifact.relative_path,
                media_type=artifact.media_type,
                byte_length=artifact.byte_length,
                content_sha256=artifact.content_sha256,
                content=artifact.content,
            )
        except PdfExtractionArtifactLimitError:
            raise
        except (TypeError, ValueError) as error:
            raise PdfExtractionArtifactMalformedError(
                f"invalid artifact payload: {error}"
            ) from error
        paths.append(artifact.relative_path)
        total_bytes += artifact.byte_length
        if artifact.relative_path == RAW_EXTRACTION_RELATIVE_PATH:
            if artifact.byte_length > artifact_limits.max_raw_extraction_bytes:
                raise PdfExtractionArtifactLimitError(
                    "raw extraction JSON exceeds max_raw_extraction_bytes"
                )
        elif artifact.byte_length > artifact_limits.max_page_text_bytes:
            raise PdfExtractionArtifactLimitError(
                "raw page text exceeds max_page_text_bytes"
            )
        if total_bytes > artifact_limits.max_total_artifact_bytes:
            raise PdfExtractionArtifactLimitError(
                "PDF extraction artifacts exceed max_total_artifact_bytes"
            )

    if len(paths) != len(set(paths)):
        raise PdfExtractionArtifactIncompleteError(
            "artifact tuple contains duplicate relative paths"
        )
    if paths[0] != RAW_EXTRACTION_RELATIVE_PATH:
        raise PdfExtractionArtifactIncompleteError(
            "artifact tuple does not begin with raw-extraction.json"
        )
    raw_artifact = artifacts[0]
    if raw_artifact.media_type != RAW_EXTRACTION_MEDIA_TYPE:
        raise PdfExtractionArtifactMalformedError(
            "raw extraction artifact media type is invalid"
        )
    try:
        raw_text = raw_artifact.content.decode("utf-8", errors="strict")
        result = deserialize_extraction_result(raw_text)
        canonical_content = (serialize_contract(result) + "\n").encode(
            "utf-8", errors="strict"
        )
    except (TypeError, UnicodeError, ValueError) as error:
        raise PdfExtractionArtifactMalformedError(
            f"raw extraction artifact is malformed: {error}"
        ) from error
    if raw_artifact.content != canonical_content:
        raise PdfExtractionArtifactMalformedError(
            "raw extraction artifact is not canonical JSON"
        )

    source = result.document.source
    if source.media_type != "application/pdf":
        raise PdfExtractionArtifactMalformedError(
            "extraction source media type is not application/pdf"
        )
    try:
        expected_digest = _validated_sha256(expected_source_sha256)
    except (TypeError, ValueError) as error:
        raise PdfExtractionArtifactMalformedError(str(error)) from error
    if (
        isinstance(expected_source_byte_size, bool)
        or not isinstance(expected_source_byte_size, int)
        or expected_source_byte_size < 0
    ):
        raise PdfExtractionArtifactMalformedError(
            "expected_source_byte_size must be a non-negative integer"
        )
    if (
        source.content_hash != expected_digest
        or source.byte_length != expected_source_byte_size
    ):
        raise PdfExtractionArtifactMalformedError(
            "extraction source does not match expected SHA-256 and byte size"
        )
    if result.manifest.status is not IngestionStatus.COMPLETED:
        raise PdfExtractionArtifactMalformedError(
            "extraction manifest status is not completed"
        )

    try:
        canonical_artifacts = _artifact_payloads(result, artifact_limits)
    except PdfExtractionArtifactLimitError:
        raise
    except (TypeError, ValueError) as error:
        raise PdfExtractionArtifactMalformedError(
            f"extraction artifacts are inconsistent: {error}"
        ) from error
    expected_paths = tuple(item.relative_path for item in canonical_artifacts)
    if tuple(paths) != expected_paths:
        raise PdfExtractionArtifactIncompleteError(
            "artifact tuple membership or order is incomplete"
        )
    try:
        PdfExtractionArtifactBundle(
            bundle_id=expected_bundle_id,
            contract_version=PDF_EXTRACTION_ARTIFACT_CONTRACT_VERSION,
            configuration=configuration,
            artifact_limits=artifact_limits,
            result=result,
            artifacts=artifacts,
        )
    except PdfExtractionArtifactLimitError:
        raise
    except (TypeError, ValueError) as error:
        raise PdfExtractionArtifactMalformedError(
            f"artifact bundle evidence is inconsistent: {error}"
        ) from error

    pages = tuple(
        PdfExtractionTranscriptPage(
            page_id=stable_id(
                "pdf-extraction-transcript-page",
                source.source_id,
                source.blob_id,
                page.page_index,
            ),
            page_index=page.page_index,
            printed_page_label=page.printed_page_label,
            text=_raw_page_text(page),
        )
        for page in result.document.pages
    )
    return PdfExtractionTranscript(
        bundle_id=expected_bundle_id,
        source_id=source.source_id,
        source_blob_id=source.blob_id,
        source_sha256=source.content_hash,
        source_byte_size=source.byte_length,
        media_type=source.media_type,
        metadata=result.document.metadata,
        manifest_id=result.manifest.manifest_id,
        status=result.manifest.status,
        review_status="automated_unreviewed",
        pages=pages,
    )


def _extract_prepared_pdf(
    content: bytes,
    source: SourceDocument,
    configuration: PdfExtractionConfiguration,
) -> ExtractionResult:
    extractor = PyMuPdfExtractor(
        low_text_character_threshold=(
            configuration.low_text_character_threshold
        ),
        maximum_pages=configuration.maximum_pages,
    )
    return extractor.extract(source, BytesIO(content))


def _artifact_payloads(
    result: ExtractionResult,
    limits: PdfExtractionArtifactLimits,
) -> tuple[PdfExtractionArtifactPayload, ...]:
    page_count = len(result.document.pages)
    page_indices = tuple(page.page_index for page in result.document.pages)
    if page_indices != tuple(range(page_count)):
        raise PdfExtractionArtifactValidationError(
            "extraction pages must be contiguous from physical page zero"
        )
    artifact_count = page_count + 1
    if artifact_count > limits.max_artifacts:
        raise PdfExtractionArtifactLimitError(
            "PDF extraction artifact count exceeds max_artifacts"
        )
    try:
        raw_extraction = (serialize_contract(result) + "\n").encode(
            "utf-8", errors="strict"
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise PdfExtractionArtifactValidationError(
            "raw extraction result is not canonical UTF-8 evidence"
        ) from error
    if len(raw_extraction) > limits.max_raw_extraction_bytes:
        raise PdfExtractionArtifactLimitError(
            "raw extraction JSON exceeds max_raw_extraction_bytes"
        )
    artifacts: list[PdfExtractionArtifactPayload] = [
        PdfExtractionArtifactPayload.create(
            relative_path=RAW_EXTRACTION_RELATIVE_PATH,
            media_type=RAW_EXTRACTION_MEDIA_TYPE,
            content=raw_extraction,
        )
    ]
    total_bytes = len(raw_extraction)
    for page in result.document.pages:
        header = (
            f"<!-- pdf-page: {page.page_index + 1}; printed-page: "
            f"{page.printed_page_label or 'unknown'} -->\n\n"
        )
        try:
            page_content = (header + _raw_page_text(page) + "\n").encode(
                "utf-8", errors="strict"
            )
        except UnicodeError as error:
            raise PdfExtractionArtifactValidationError(
                "raw page text contains invalid Unicode"
            ) from error
        if len(page_content) > limits.max_page_text_bytes:
            raise PdfExtractionArtifactLimitError(
                "raw page text exceeds max_page_text_bytes"
            )
        total_bytes += len(page_content)
        if total_bytes > limits.max_total_artifact_bytes:
            raise PdfExtractionArtifactLimitError(
                "PDF extraction artifacts exceed max_total_artifact_bytes"
            )
        artifacts.append(
            PdfExtractionArtifactPayload.create(
                relative_path=(
                    f"{RAW_PAGE_DIRECTORY}/page-{page.page_index + 1:04d}.txt"
                ),
                media_type=RAW_PAGE_TEXT_MEDIA_TYPE,
                content=page_content,
            )
        )
    if total_bytes > limits.max_total_artifact_bytes:
        raise PdfExtractionArtifactLimitError(
            "PDF extraction artifacts exceed max_total_artifact_bytes"
        )
    return tuple(artifacts)


def _raw_page_text(page: ExtractedPage) -> str:
    return "\n\n".join(
        block.text
        for block in page.blocks
        if block.kind == "text" and block.text is not None
    )


def _bundle_id(
    *,
    configuration: PdfExtractionConfiguration,
    artifact_limits: PdfExtractionArtifactLimits,
    result: ExtractionResult,
    artifacts: tuple[PdfExtractionArtifactPayload, ...],
) -> str:
    return stable_id(
        "pdf-extraction-artifact-bundle",
        PDF_EXTRACTION_ARTIFACT_CONTRACT_VERSION,
        configuration,
        artifact_limits,
        result.manifest.manifest_id,
        tuple(
            (
                item.relative_path,
                item.media_type,
                item.byte_length,
                item.content_sha256,
            )
            for item in artifacts
        ),
    )


def _validate_relative_path(value: str) -> None:
    _bounded_text("relative_path", value, _HARD_MAX_RELATIVE_PATH_BYTES)
    if "\\" in value:
        raise PdfExtractionArtifactValidationError(
            "artifact relative path must use POSIX separators"
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise PdfExtractionArtifactValidationError(
            "artifact relative path must be canonical and confined"
        )


def _validated_sha256(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("expected_source_sha256 must be a string")
    if len(value) != 64 or value != value.lower():
        raise PdfSourceIntegrityError(
            "expected_source_sha256 must be lowercase SHA-256 hexadecimal"
        )
    try:
        int(value, 16)
    except ValueError as error:
        raise PdfSourceIntegrityError(
            "expected_source_sha256 must be lowercase SHA-256 hexadecimal"
        ) from error
    return value


def _bounded_text(name: str, value: str, maximum: int) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise ValueError(f"{name} must be valid UTF-8 text") from error
    if (
        not value
        or len(encoded) > maximum
        or any(
            ord(character) < 32 or 127 <= ord(character) <= 159
            for character in value
        )
    ):
        raise ValueError(f"{name} must be nonempty, control-free, and bounded")
