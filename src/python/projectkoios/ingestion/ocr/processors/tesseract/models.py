from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.ocr.models import (
    OCRConfiguration,
    OCRFailureKind,
    OCRLanguageResourceIdentity,
)
from projectkoios.ingestion.ocr.processors.tesseract.base import (
    BaseTesseractModel,
)
from projectkoios.ingestion.ocr.processors.tesseract.constants import (
    MAX_CAPTURE_BYTES,
    MAX_RESOURCE_BYTES,
    MAX_TIMEOUT_MILLISECONDS,
    MAX_TOTAL_RESOURCE_BYTES,
    SUPPORTED_PAGE_SEGMENTATION_MODES,
    TESSERACT_ADAPTER_VERSION,
)
from projectkoios.ingestion.ocr.processors.tesseract.errors import (
    TesseractAdapterConfigurationError,
)


@dataclass(frozen=True)
class TesseractAdapterConfiguration(BaseTesseractModel):
    """Deterministic invocation choices and adapter-side safety limits."""

    timeout_milliseconds: int = 30_000
    max_stdout_bytes: int = 16_000_000
    max_stderr_bytes: int = 1_000_000
    max_resource_bytes: int = 128_000_000
    max_total_resource_bytes: int = 512_000_000
    page_segmentation_mode: int = 6
    engine_mode: int | None = None

    def __post_init__(self) -> None:
        for name, value, hard_maximum in (
            (
                "timeout_milliseconds",
                self.timeout_milliseconds,
                MAX_TIMEOUT_MILLISECONDS,
            ),
            ("max_stdout_bytes", self.max_stdout_bytes, MAX_CAPTURE_BYTES),
            ("max_stderr_bytes", self.max_stderr_bytes, MAX_CAPTURE_BYTES),
            (
                "max_resource_bytes",
                self.max_resource_bytes,
                MAX_RESOURCE_BYTES,
            ),
            (
                "max_total_resource_bytes",
                self.max_total_resource_bytes,
                MAX_TOTAL_RESOURCE_BYTES,
            ),
        ):
            self._positive_integer(name, value)
            if value > hard_maximum:
                raise TesseractAdapterConfigurationError(
                    f"{name} exceeds the implementation maximum "
                    f"({hard_maximum})"
                )
        self._nonnegative_integer(
            "page_segmentation_mode",
            self.page_segmentation_mode,
        )
        if self.page_segmentation_mode not in SUPPORTED_PAGE_SEGMENTATION_MODES:
            supported = ", ".join(
                str(value)
                for value in sorted(SUPPORTED_PAGE_SEGMENTATION_MODES)
            )
            raise TesseractAdapterConfigurationError(
                "page_segmentation_mode must be an OCR mode that does not "
                f"require implicit OSD resources ({supported})"
            )
        if self.engine_mode is not None:
            self._nonnegative_integer("engine_mode", self.engine_mode)
            if self.engine_mode > 3:
                raise TesseractAdapterConfigurationError(
                    "engine_mode must be between 0 and 3"
                )
        if self.max_total_resource_bytes < self.max_resource_bytes:
            raise TesseractAdapterConfigurationError(
                "max_total_resource_bytes cannot be smaller than "
                "max_resource_bytes"
            )

    @property
    def configuration_digest(self) -> str:
        return stable_id(
            "tesseract-adapter-configuration",
            TESSERACT_ADAPTER_VERSION,
            self.identity_parts(),
        )

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.timeout_milliseconds,
            self.max_stdout_bytes,
            self.max_stderr_bytes,
            self.max_resource_bytes,
            self.max_total_resource_bytes,
            self.page_segmentation_mode,
            self.engine_mode,
        )


@dataclass(frozen=True)
class TesseractLanguageBinding(BaseTesseractModel):
    """Map one semantic OCR language to one explicit traineddata file."""

    language: str
    resource_name: str
    traineddata_path: Path

    def __post_init__(self) -> None:
        canonical = OCRConfiguration(languages=(self.language,)).languages[0]
        object.__setattr__(self, "language", canonical)
        self._bounded_identity_string("resource_name", self.resource_name)
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*"
            r"(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*",
            self.resource_name,
        ):
            raise TesseractAdapterConfigurationError(
                "resource_name must be a safe Tesseract language name"
            )
        if not isinstance(self.traineddata_path, Path):
            raise TypeError("traineddata_path must be a pathlib.Path")
        object.__setattr__(
            self,
            "traineddata_path",
            self.traineddata_path.expanduser().resolve(strict=False),
        )


@dataclass(frozen=True)
class ProcessCapture:
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    stdout_limit_exceeded: bool = False
    stderr_limit_exceeded: bool = False


@dataclass(frozen=True)
class BackendInspection:
    executable: Path | None
    executable_sha256: str | None
    backend_version: str
    language_resources: tuple[OCRLanguageResourceIdentity, ...]
    binding_by_language: tuple[tuple[str, TesseractLanguageBinding], ...]
    issue_kind: OCRFailureKind | None = None
    issue_code: str | None = None
    issue_message: str | None = None
    issue_retryable: bool = False


@dataclass(frozen=True)
class ParsedWord:
    text: str
    pixel_bounding_box: tuple[float, float, float, float]
    confidence: float | None
    line_key: tuple[int, int, int, int]


@dataclass(frozen=True)
class ParsedLine:
    text: str
    pixel_bounding_box: tuple[float, float, float, float]
    confidence: float | None
    words: tuple[ParsedWord, ...]


class IdentityKeywords(TypedDict):
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str


__all__ = [
    "TesseractAdapterConfiguration",
    "TesseractLanguageBinding",
]
