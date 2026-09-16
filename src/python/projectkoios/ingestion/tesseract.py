from __future__ import annotations

import hashlib
import math
import os
import re
import selectors
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TypedDict

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.models import WarningSeverity
from projectkoios.ingestion.ocr import (
    OCRConfidence,
    OCRConfiguration,
    OCRContractLimitError,
    OCRFailure,
    OCRFailureKind,
    OCRLanguageResourceIdentity,
    OCRLine,
    OCROutputMode,
    OCRProcessorIdentity,
    OCRRequest,
    OCRResourceIdentityKind,
    OCRResult,
    OCRSelection,
    OCRSelectionResult,
    OCRSelectionStatus,
    OCRToken,
    OCRWarning,
)

TESSERACT_ADAPTER_VERSION = "1"
TESSERACT_BACKEND_NAME = "tesseract"
_TESSERACT_TSV_HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\t"
    "top\twidth\theight\tconf\ttext"
)
_MAX_TIMEOUT_MILLISECONDS = 300_000
_MAX_CAPTURE_BYTES = 64_000_000
_MAX_RESOURCE_BYTES = 256_000_000
_MAX_TOTAL_RESOURCE_BYTES = 1_000_000_000
_MAX_EXECUTABLE_BYTES = 256_000_000
_MAX_BINDINGS = 64
_MAX_IDENTITY_CHARACTERS = 4_096
_READ_CHUNK_BYTES = 65_536
_VERSION_CAPTURE_BYTES = 65_536
_SUPPORTED_PAGE_SEGMENTATION_MODES = frozenset(
    {3, 4, 5, 6, 7, 8, 9, 10, 11, 13}
)


class TesseractAdapterConfigurationError(ValueError):
    """Raised when adapter construction is invalid or exceeds hard bounds."""


@dataclass(frozen=True)
class TesseractAdapterConfiguration:
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
                _MAX_TIMEOUT_MILLISECONDS,
            ),
            ("max_stdout_bytes", self.max_stdout_bytes, _MAX_CAPTURE_BYTES),
            ("max_stderr_bytes", self.max_stderr_bytes, _MAX_CAPTURE_BYTES),
            (
                "max_resource_bytes",
                self.max_resource_bytes,
                _MAX_RESOURCE_BYTES,
            ),
            (
                "max_total_resource_bytes",
                self.max_total_resource_bytes,
                _MAX_TOTAL_RESOURCE_BYTES,
            ),
        ):
            _positive_integer(name, value)
            if value > hard_maximum:
                raise TesseractAdapterConfigurationError(
                    f"{name} exceeds the implementation maximum "
                    f"({hard_maximum})"
                )
        _nonnegative_integer(
            "page_segmentation_mode", self.page_segmentation_mode
        )
        if self.page_segmentation_mode not in (
            _SUPPORTED_PAGE_SEGMENTATION_MODES
        ):
            supported = ", ".join(
                str(value)
                for value in sorted(_SUPPORTED_PAGE_SEGMENTATION_MODES)
            )
            raise TesseractAdapterConfigurationError(
                "page_segmentation_mode must be an OCR mode that does not "
                f"require implicit OSD resources ({supported})"
            )
        if self.engine_mode is not None:
            _nonnegative_integer("engine_mode", self.engine_mode)
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
class TesseractLanguageBinding:
    """Map one semantic OCR language to one explicit traineddata file."""

    language: str
    resource_name: str
    traineddata_path: Path

    def __post_init__(self) -> None:
        canonical = OCRConfiguration(languages=(self.language,)).languages[0]
        object.__setattr__(self, "language", canonical)
        _bounded_identity_string("resource_name", self.resource_name)
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
class _ProcessCapture:
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    stdout_limit_exceeded: bool = False
    stderr_limit_exceeded: bool = False


@dataclass(frozen=True)
class _BackendInspection:
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
class _ParsedWord:
    text: str
    pixel_bounding_box: tuple[float, float, float, float]
    confidence: float | None
    line_key: tuple[int, int, int, int]


@dataclass(frozen=True)
class _ParsedLine:
    text: str
    pixel_bounding_box: tuple[float, float, float, float]
    confidence: float | None
    words: tuple[_ParsedWord, ...]


class _IdentityKeywords(TypedDict):
    processor_name: str
    processor_version: str
    backend_name: str
    backend_version: str


class TesseractOCRProcessor:
    """Bounded subprocess adapter for explicit Tesseract OCR selections."""

    name = "tesseract-ocr-adapter"

    def __init__(
        self,
        *,
        language_bindings: tuple[TesseractLanguageBinding, ...],
        executable: str | Path = "tesseract",
        configuration: TesseractAdapterConfiguration | None = None,
    ) -> None:
        if not isinstance(language_bindings, tuple):
            raise TypeError("language_bindings must be an immutable tuple")
        if not language_bindings:
            raise TesseractAdapterConfigurationError(
                "at least one language binding is required"
            )
        if len(language_bindings) > _MAX_BINDINGS:
            raise TesseractAdapterConfigurationError(
                "too many Tesseract language bindings"
            )
        if any(
            not isinstance(binding, TesseractLanguageBinding)
            for binding in language_bindings
        ):
            raise TypeError(
                "language_bindings must contain TesseractLanguageBinding values"
            )
        languages = tuple(binding.language for binding in language_bindings)
        if len(set(languages)) != len(languages):
            raise TesseractAdapterConfigurationError(
                "semantic language bindings must be unique"
            )
        resources: dict[str, Path] = {}
        for binding in language_bindings:
            previous = resources.get(binding.resource_name)
            if previous is not None and previous != binding.traineddata_path:
                raise TesseractAdapterConfigurationError(
                    "one Tesseract resource name cannot refer to multiple files"
                )
            resources[binding.resource_name] = binding.traineddata_path
        if isinstance(executable, Path):
            executable_value = str(
                executable.expanduser().resolve(strict=False)
            )
        elif isinstance(executable, str):
            executable_value = executable
            if os.sep in executable_value or (
                os.altsep is not None and os.altsep in executable_value
            ):
                executable_value = str(
                    Path(executable_value).expanduser().resolve(strict=False)
                )
        else:
            raise TypeError("executable must be a string or pathlib.Path")
        _bounded_identity_string("executable", executable_value)
        if "\x00" in executable_value:
            raise TesseractAdapterConfigurationError(
                "executable cannot contain a NUL character"
            )
        actual_configuration = configuration or TesseractAdapterConfiguration()
        if not isinstance(actual_configuration, TesseractAdapterConfiguration):
            raise TypeError(
                "configuration must be TesseractAdapterConfiguration"
            )
        self.language_bindings = language_bindings
        self.executable = executable_value
        self.configuration = actual_configuration
        digest = actual_configuration.configuration_digest.rsplit(":", 1)[-1]
        self.version = f"{TESSERACT_ADAPTER_VERSION}+{digest}"

    def identity_for(self, request: OCRRequest) -> OCRProcessorIdentity:
        """Resolve engine version and exact requested language resources."""
        inspection = self._inspect(request)
        return self._processor_identity(inspection)

    def process(self, request: OCRRequest) -> OCRResult:
        """Run bounded subprocesses and preserve mixed selection outcomes."""
        if not isinstance(request, OCRRequest):
            raise TypeError("request must be an OCRRequest")
        inspection = self._inspect(request)
        identity = self._processor_identity(inspection)
        if inspection.issue_kind is not None:
            return self._failed_result_for_all(request, identity, inspection)
        if inspection.executable is None:
            raise RuntimeError("usable inspection has no executable")

        with tempfile.TemporaryDirectory(prefix="koios-ocr-") as temporary:
            temporary_path = Path(temporary)
            tessdata_path = temporary_path / "tessdata"
            images_path = temporary_path / "images"
            tessdata_path.mkdir(mode=0o700)
            images_path.mkdir(mode=0o700)
            staging_issue = self._stage_resources(inspection, tessdata_path)
            if staging_issue is not None:
                return self._failed_result_for_all(
                    request, identity, staging_issue
                )

            resource_names = _unique_in_order(
                binding.resource_name
                for _, binding in inspection.binding_by_language
            )
            selection_results: list[OCRSelectionResult] = []
            for index, selection in enumerate(request.selections):
                input_path = images_path / f"selection-{index:06d}.png"
                try:
                    _write_exclusive(
                        input_path, selection.image.rendered_region.content
                    )
                except OSError:
                    selection_results.append(
                        self._failed_selection(
                            selection=selection,
                            request=request,
                            identity=identity,
                            kind=OCRFailureKind.PROCESSOR_ERROR,
                            code="ocr.tesseract.input_staging_error",
                            message=(
                                "OCR input could not be staged for Tesseract"
                            ),
                            retryable=True,
                            evidence=(),
                        )
                    )
                    continue
                selection_result = self._process_selection(
                    selection=selection,
                    request=request,
                    identity=identity,
                    executable=inspection.executable,
                    input_path=input_path,
                    tessdata_path=tessdata_path,
                    resource_names=resource_names,
                    temporary_path=temporary_path,
                )
                if _exceeds_aggregate_limits(
                    (*selection_results, selection_result),
                    request.configuration,
                ):
                    selection_result = self._failed_selection(
                        selection=selection,
                        request=request,
                        identity=identity,
                        kind=OCRFailureKind.RESOURCE_LIMIT,
                        code="ocr.tesseract.aggregate_result_limit",
                        message=(
                            "Tesseract output exceeded aggregate OCR limits"
                        ),
                        retryable=False,
                        evidence=(),
                    )
                selection_results.append(selection_result)
        try:
            return OCRResult.create(
                request=request,
                selection_results=tuple(selection_results),
                processor_identity=identity,
            )
        except OCRContractLimitError:
            fallback = tuple(
                self._failed_selection(
                    selection=selection,
                    request=request,
                    identity=identity,
                    kind=OCRFailureKind.RESOURCE_LIMIT,
                    code="ocr.tesseract.aggregate_result_limit",
                    message="Tesseract output exceeded aggregate OCR limits",
                    retryable=False,
                    evidence=(),
                )
                for selection in request.selections
            )
            return OCRResult.create(
                request=request,
                selection_results=fallback,
                processor_identity=identity,
            )

    def _inspect(self, request: OCRRequest) -> _BackendInspection:
        if not isinstance(request, OCRRequest):
            raise TypeError("request must be an OCRRequest")
        executable = _resolve_executable(self.executable)
        backend_version = "unavailable"
        executable_sha256: str | None = None
        issue_kind: OCRFailureKind | None = None
        issue_code: str | None = None
        issue_message: str | None = None
        issue_retryable = False
        if executable is None:
            issue_kind = OCRFailureKind.PROCESSOR_UNAVAILABLE
            issue_code = "ocr.tesseract.executable_unavailable"
            issue_message = "Tesseract executable is unavailable"
        else:
            version_capture = _run_bounded(
                (str(executable), "--version"),
                cwd=None,
                environment=_base_environment(None),
                timeout_milliseconds=5_000,
                max_stdout_bytes=_VERSION_CAPTURE_BYTES,
                max_stderr_bytes=_VERSION_CAPTURE_BYTES,
            )
            backend_version = _parse_tesseract_version(version_capture)
            if backend_version == "unavailable":
                issue_kind = OCRFailureKind.PROCESSOR_UNAVAILABLE
                issue_code = "ocr.tesseract.version_unavailable"
                issue_message = "Tesseract version could not be determined"
                issue_retryable = version_capture.timed_out
            else:
                (
                    executable_sha256,
                    _executable_size,
                    executable_issue,
                ) = _hash_bounded_file(executable, _MAX_EXECUTABLE_BYTES)
                if executable_issue is not None or executable_sha256 is None:
                    if executable_issue == "resource-size-limit":
                        issue_kind = OCRFailureKind.RESOURCE_LIMIT
                        issue_code = "ocr.tesseract.executable_limit"
                        issue_message = (
                            "Tesseract executable exceeds adapter limits"
                        )
                    else:
                        issue_kind = OCRFailureKind.PROCESSOR_UNAVAILABLE
                        issue_code = (
                            "ocr.tesseract.executable_identity_unavailable"
                        )
                        issue_message = (
                            "Tesseract executable identity could not be "
                            "determined"
                        )
                    backend_version = "unavailable"
                else:
                    backend_version = (
                        f"{backend_version}+binary-sha256:"
                        f"{executable_sha256}"
                    )

        by_language = {
            binding.language: binding for binding in self.language_bindings
        }
        identities: list[OCRLanguageResourceIdentity] = []
        requested_bindings: list[tuple[str, TesseractLanguageBinding]] = []
        resource_by_name: dict[
            str, tuple[str | None, int, str | None]
        ] = {}
        total_resource_bytes = 0
        for language in request.configuration.languages:
            binding = by_language.get(language)
            if binding is None:
                identities.append(
                    OCRLanguageResourceIdentity(
                        language=language,
                        resource_name="unmapped",
                        identity_kind=OCRResourceIdentityKind.EXPLICIT,
                        resource_identity="unavailable",
                    )
                )
                if issue_kind is None:
                    issue_kind = OCRFailureKind.UNSUPPORTED_LANGUAGE
                    issue_code = "ocr.tesseract.language_unmapped"
                    issue_message = (
                        "No Tesseract resource is bound to a requested language"
                    )
                continue
            requested_bindings.append((language, binding))
            observation = resource_by_name.get(binding.resource_name)
            if observation is None:
                remaining_resource_bytes = (
                    self.configuration.max_total_resource_bytes
                    - total_resource_bytes
                )
                digest: str | None
                size: int
                resource_issue: str | None
                if remaining_resource_bytes <= 0:
                    digest, size, resource_issue = (
                        None,
                        0,
                        "resource-total-limit",
                    )
                else:
                    read_limit = min(
                        self.configuration.max_resource_bytes,
                        remaining_resource_bytes,
                    )
                    digest, size, resource_issue = _hash_bounded_file(
                        binding.traineddata_path,
                        read_limit,
                    )
                    if (
                        resource_issue == "resource-size-limit"
                        and read_limit < self.configuration.max_resource_bytes
                    ):
                        resource_issue = "resource-total-limit"
                total_resource_bytes += size
                observation = (digest, size, resource_issue)
                resource_by_name[binding.resource_name] = observation
            digest, _size, resource_issue = observation
            if resource_issue is None and digest is not None:
                identities.append(
                    OCRLanguageResourceIdentity(
                        language=language,
                        resource_name=binding.resource_name,
                        identity_kind=OCRResourceIdentityKind.SHA256,
                        resource_identity=digest,
                    )
                )
            else:
                identities.append(
                    OCRLanguageResourceIdentity(
                        language=language,
                        resource_name=binding.resource_name,
                        identity_kind=OCRResourceIdentityKind.EXPLICIT,
                        resource_identity=resource_issue or "unavailable",
                    )
                )
                if issue_kind is None:
                    if resource_issue in {
                        "resource-size-limit",
                        "resource-total-limit",
                    }:
                        issue_kind = OCRFailureKind.RESOURCE_LIMIT
                        issue_code = "ocr.tesseract.resource_limit"
                        issue_message = (
                            "Tesseract language resources exceed adapter limits"
                        )
                    else:
                        issue_kind = OCRFailureKind.PROCESSOR_UNAVAILABLE
                        issue_code = "ocr.tesseract.resource_unavailable"
                        issue_message = (
                            "A requested Tesseract language resource is "
                            "unavailable"
                        )
        return _BackendInspection(
            executable=executable,
            executable_sha256=executable_sha256,
            backend_version=backend_version,
            language_resources=tuple(identities),
            binding_by_language=tuple(requested_bindings),
            issue_kind=issue_kind,
            issue_code=issue_code,
            issue_message=issue_message,
            issue_retryable=issue_retryable,
        )

    def _processor_identity(
        self, inspection: _BackendInspection
    ) -> OCRProcessorIdentity:
        return OCRProcessorIdentity(
            processor_name=self.name,
            processor_version=self.version,
            backend_name=TESSERACT_BACKEND_NAME,
            backend_version=inspection.backend_version,
            language_resources=inspection.language_resources,
        )

    def _stage_resources(
        self,
        inspection: _BackendInspection,
        destination: Path,
    ) -> _BackendInspection | None:
        if (
            inspection.executable is None
            or inspection.executable_sha256 is None
        ):
            raise RuntimeError("usable inspection has no executable identity")
        executable_digest, _, executable_issue = _hash_bounded_file(
            inspection.executable, _MAX_EXECUTABLE_BYTES
        )
        if executable_issue == "resource-size-limit":
            return _inspection_issue(
                inspection,
                kind=OCRFailureKind.RESOURCE_LIMIT,
                code="ocr.tesseract.executable_limit",
                message="Tesseract executable exceeds adapter limits",
            )
        if (
            executable_issue is not None
            or executable_digest != inspection.executable_sha256
        ):
            return _inspection_issue(
                inspection,
                kind=OCRFailureKind.PROCESSOR_UNAVAILABLE,
                code="ocr.tesseract.executable_changed",
                message="Tesseract executable changed before execution",
                retryable=True,
            )
        expected_by_name: dict[str, str] = {}
        binding_by_name: dict[str, TesseractLanguageBinding] = {}
        for identity, (_, binding) in zip(
            inspection.language_resources,
            inspection.binding_by_language,
            strict=True,
        ):
            if identity.identity_kind is not OCRResourceIdentityKind.SHA256:
                return _inspection_issue(
                    inspection,
                    kind=OCRFailureKind.PROCESSOR_UNAVAILABLE,
                    code="ocr.tesseract.resource_unavailable",
                    message=(
                        "A requested Tesseract language resource is unavailable"
                    ),
                )
            expected_by_name.setdefault(
                binding.resource_name, identity.resource_identity
            )
            binding_by_name.setdefault(binding.resource_name, binding)
        total = 0
        for resource_name, binding in binding_by_name.items():
            target = destination / f"{resource_name}.traineddata"
            try:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                digest, size = _copy_bounded_file(
                    binding.traineddata_path,
                    target,
                    self.configuration.max_resource_bytes,
                )
            except OCRContractLimitError:
                return _inspection_issue(
                    inspection,
                    kind=OCRFailureKind.RESOURCE_LIMIT,
                    code="ocr.tesseract.resource_limit",
                    message=(
                        "Tesseract language resources exceed adapter limits"
                    ),
                )
            except OSError:
                return _inspection_issue(
                    inspection,
                    kind=OCRFailureKind.PROCESSOR_UNAVAILABLE,
                    code="ocr.tesseract.resource_unavailable",
                    message=(
                        "A requested Tesseract language resource is unavailable"
                    ),
                )
            total += size
            if total > self.configuration.max_total_resource_bytes:
                return _inspection_issue(
                    inspection,
                    kind=OCRFailureKind.RESOURCE_LIMIT,
                    code="ocr.tesseract.resource_limit",
                    message=(
                        "Tesseract language resources exceed adapter limits"
                    ),
                )
            if digest != expected_by_name[resource_name]:
                return _inspection_issue(
                    inspection,
                    kind=OCRFailureKind.PROCESSOR_UNAVAILABLE,
                    code="ocr.tesseract.resource_changed",
                    message=(
                        "A Tesseract language resource changed before execution"
                    ),
                    retryable=True,
                )
        return None

    def _process_selection(
        self,
        *,
        selection: OCRSelection,
        request: OCRRequest,
        identity: OCRProcessorIdentity,
        executable: Path,
        input_path: Path,
        tessdata_path: Path,
        resource_names: tuple[str, ...],
        temporary_path: Path,
    ) -> OCRSelectionResult:
        command = [
            str(executable),
            str(input_path),
            "stdout",
            "--tessdata-dir",
            str(tessdata_path),
            "--dpi",
            str(selection.image.rendered_region.resolution_dpi),
            "-l",
            "+".join(resource_names),
            "--psm",
            str(self.configuration.page_segmentation_mode),
        ]
        if self.configuration.engine_mode is not None:
            command.extend(("--oem", str(self.configuration.engine_mode)))
        command.extend(("-c", "tessedit_create_tsv=1"))
        capture = _run_bounded(
            tuple(command),
            cwd=temporary_path,
            environment=_base_environment(temporary_path),
            timeout_milliseconds=self.configuration.timeout_milliseconds,
            max_stdout_bytes=self.configuration.max_stdout_bytes,
            max_stderr_bytes=self.configuration.max_stderr_bytes,
        )
        if capture.stdout_limit_exceeded or capture.stderr_limit_exceeded:
            return self._failed_selection(
                selection=selection,
                request=request,
                identity=identity,
                kind=OCRFailureKind.RESOURCE_LIMIT,
                code="ocr.tesseract.output_limit",
                message="Tesseract process output exceeded adapter limits",
                retryable=False,
                evidence=(),
            )

        invocation_failure: (
            tuple[OCRFailureKind, str, str, bool, tuple[tuple[str, str], ...]]
            | None
        ) = None
        if capture.timed_out:
            invocation_failure = (
                OCRFailureKind.RESOURCE_LIMIT,
                "ocr.tesseract.timeout",
                "Tesseract processing exceeded the configured timeout",
                True,
                (),
            )
        elif capture.returncode != 0:
            failure_evidence: tuple[tuple[str, str], ...] = (
                ("returncode", str(capture.returncode)),
            )
            invocation_failure = (
                OCRFailureKind.PROCESSOR_ERROR,
                "ocr.tesseract.process_error",
                "Tesseract processing failed",
                True,
                failure_evidence,
            )

        try:
            parsed_lines = _parse_tsv(capture.stdout, request.configuration)
            warning: OCRWarning | None = None
            failure: OCRFailure | None = None
            status = OCRSelectionStatus.COMPLETED
            if invocation_failure is not None:
                kind, code, message, retryable, evidence = invocation_failure
                warning = OCRWarning.create(
                    selection_id=selection.selection_id,
                    code=code,
                    severity=WarningSeverity.ERROR,
                    message=message,
                    evidence=evidence,
                )
                failure = OCRFailure.create(
                    selection_id=selection.selection_id,
                    kind=kind,
                    message=message,
                    retryable=retryable,
                    warning_ids=(warning.warning_id,),
                )
            tokens, lines = _build_outputs(
                selection=selection,
                configuration=request.configuration,
                identity=identity,
                parsed_lines=parsed_lines,
                warning_ids=(warning.warning_id,)
                if warning is not None
                else (),
            )
            if invocation_failure is not None:
                status = (
                    OCRSelectionStatus.PARTIAL
                    if tokens or lines
                    else OCRSelectionStatus.FAILED
                )
            return OCRSelectionResult.create(
                selection=selection,
                configuration=request.configuration,
                status=status,
                tokens=tokens,
                lines=lines,
                warnings=(warning,) if warning is not None else (),
                failure=failure,
                **_identity_keywords(identity),
            )
        except OCRContractLimitError as error:
            return self._failed_selection(
                selection=selection,
                request=request,
                identity=identity,
                kind=OCRFailureKind.RESOURCE_LIMIT,
                code="ocr.tesseract.result_limit",
                message="Tesseract output exceeded OCR contract limits",
                retryable=False,
                evidence=(("reason", _bounded_reason(error)),),
            )
        except (TypeError, ValueError, UnicodeError) as error:
            if invocation_failure is not None:
                kind, code, message, retryable, evidence = invocation_failure
                parse_reason = _bounded_reason(error)
                if parse_reason:
                    evidence += (("output_reason", parse_reason),)
                return self._failed_selection(
                    selection=selection,
                    request=request,
                    identity=identity,
                    kind=kind,
                    code=code,
                    message=message,
                    retryable=retryable,
                    evidence=evidence,
                )
            return self._failed_selection(
                selection=selection,
                request=request,
                identity=identity,
                kind=OCRFailureKind.OUTPUT_INVALID,
                code="ocr.tesseract.output_invalid",
                message="Tesseract returned invalid TSV output",
                retryable=False,
                evidence=(("reason", _bounded_reason(error)),),
            )

    def _failed_result_for_all(
        self,
        request: OCRRequest,
        identity: OCRProcessorIdentity,
        inspection: _BackendInspection,
    ) -> OCRResult:
        if (
            inspection.issue_kind is None
            or inspection.issue_code is None
            or inspection.issue_message is None
        ):
            raise RuntimeError("failed inspection has incomplete evidence")
        selection_results = tuple(
            self._failed_selection(
                selection=selection,
                request=request,
                identity=identity,
                kind=inspection.issue_kind,
                code=inspection.issue_code,
                message=inspection.issue_message,
                retryable=inspection.issue_retryable,
                evidence=(),
            )
            for selection in request.selections
        )
        return OCRResult.create(
            request=request,
            selection_results=selection_results,
            processor_identity=identity,
        )

    def _failed_selection(
        self,
        *,
        selection: OCRSelection,
        request: OCRRequest,
        identity: OCRProcessorIdentity,
        kind: OCRFailureKind,
        code: str,
        message: str,
        retryable: bool,
        evidence: tuple[tuple[str, str], ...],
    ) -> OCRSelectionResult:
        bounded_message = message[
            : request.configuration.max_warning_message_characters
        ]
        bounded_evidence = tuple(
            (
                key,
                value[
                    : request.configuration.max_warning_message_characters
                ],
            )
            for key, value in evidence[
                : request.configuration.max_warning_evidence_entries
            ]
        )
        warning = OCRWarning.create(
            selection_id=selection.selection_id,
            code=code,
            severity=WarningSeverity.ERROR,
            message=bounded_message,
            evidence=bounded_evidence,
        )
        failure = OCRFailure.create(
            selection_id=selection.selection_id,
            kind=kind,
            message=bounded_message,
            retryable=retryable,
            warning_ids=(warning.warning_id,),
        )
        return OCRSelectionResult.create(
            selection=selection,
            configuration=request.configuration,
            status=OCRSelectionStatus.FAILED,
            warnings=(warning,),
            failure=failure,
            **_identity_keywords(identity),
        )


def _exceeds_aggregate_limits(
    selection_results: tuple[OCRSelectionResult, ...],
    configuration: OCRConfiguration,
) -> bool:
    token_count = sum(len(item.tokens) for item in selection_results)
    line_count = sum(len(item.lines) for item in selection_results)
    warning_count = sum(len(item.warnings) for item in selection_results)
    text_characters = sum(
        sum(len(token.text) for token in item.tokens)
        + sum(len(line.text) for line in item.lines)
        for item in selection_results
    )
    return (
        token_count > configuration.max_total_tokens
        or line_count > configuration.max_total_lines
        or warning_count > configuration.max_total_warnings
        or text_characters > configuration.max_total_text_characters
    )


def _build_outputs(
    *,
    selection: OCRSelection,
    configuration: OCRConfiguration,
    identity: OCRProcessorIdentity,
    parsed_lines: tuple[_ParsedLine, ...],
    warning_ids: tuple[str, ...],
) -> tuple[tuple[OCRToken, ...], tuple[OCRLine, ...]]:
    mode = configuration.output_mode
    include_tokens = mode in (
        OCROutputMode.TOKENS,
        OCROutputMode.TOKENS_AND_LINES,
    )
    include_lines = mode in (
        OCROutputMode.LINES,
        OCROutputMode.TOKENS_AND_LINES,
    )
    tokens: list[OCRToken] = []
    token_ids_by_line: list[tuple[str, ...]] = []
    token_order = 0
    for line_order, parsed_line in enumerate(parsed_lines):
        line_token_ids: list[str] = []
        if include_tokens:
            for word in parsed_line.words:
                token = OCRToken.create(
                    selection=selection,
                    configuration=configuration,
                    text=word.text,
                    pixel_bounding_box=word.pixel_bounding_box,
                    confidence=_word_confidence(word.confidence),
                    order=token_order,
                    line_order=(
                        line_order
                        if mode is OCROutputMode.TOKENS_AND_LINES
                        else None
                    ),
                    warning_ids=warning_ids,
                    **_identity_keywords(identity),
                )
                tokens.append(token)
                line_token_ids.append(token.token_id)
                token_order += 1
        token_ids_by_line.append(tuple(line_token_ids))

    lines: list[OCRLine] = []
    if include_lines:
        for order, parsed_line in enumerate(parsed_lines):
            lines.append(
                OCRLine.create(
                    selection=selection,
                    configuration=configuration,
                    text=parsed_line.text,
                    pixel_bounding_box=parsed_line.pixel_bounding_box,
                    confidence=_line_confidence(parsed_line.confidence),
                    order=order,
                    token_ids=(
                        token_ids_by_line[order]
                        if mode is OCROutputMode.TOKENS_AND_LINES
                        else ()
                    ),
                    warning_ids=warning_ids,
                    **_identity_keywords(identity),
                )
            )
    return tuple(tokens), tuple(lines)


def _parse_tsv(
    payload: bytes, configuration: OCRConfiguration
) -> tuple[_ParsedLine, ...]:
    if len(payload) > _MAX_CAPTURE_BYTES:
        raise OCRContractLimitError("TSV output exceeds the safety limit")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("TSV output is not valid UTF-8") from error
    if "\x00" in text:
        raise ValueError("TSV output contains a NUL character")
    rows = text.splitlines()
    if not rows or rows[0] != _TESSERACT_TSV_HEADER:
        raise ValueError("TSV output has an unsupported header")
    grouped: dict[tuple[int, int, int, int], list[_ParsedWord]] = {}
    last_word_number: dict[tuple[int, int, int, int], int] = {}
    word_count = 0
    text_characters = 0
    for row_number, row in enumerate(rows[1:], start=2):
        if not row:
            continue
        columns = row.split("\t", 11)
        if len(columns) != 12:
            raise ValueError(f"TSV row {row_number} has the wrong column count")
        numeric = tuple(
            _tsv_integer(value, row_number) for value in columns[:10]
        )
        (
            level,
            page_number,
            block_number,
            paragraph_number,
            line_number,
            word_number,
            left,
            top,
            width,
            height,
        ) = numeric
        if level not in {1, 2, 3, 4, 5}:
            raise ValueError(f"TSV row {row_number} has an unsupported level")
        if page_number != 1:
            raise ValueError(f"TSV row {row_number} refers to another page")
        if level != 5:
            continue
        token_text = columns[11].strip()
        if not token_text:
            continue
        if min(block_number, paragraph_number, line_number, word_number) <= 0:
            raise ValueError(
                f"TSV row {row_number} has invalid word hierarchy"
            )
        line_key = (
            page_number,
            block_number,
            paragraph_number,
            line_number,
        )
        if word_number <= last_word_number.get(line_key, 0):
            raise ValueError(
                f"TSV row {row_number} has duplicate or unordered words"
            )
        last_word_number[line_key] = word_number
        if width <= 0 or height <= 0:
            raise ValueError(f"TSV row {row_number} has an empty word box")
        right = left + width
        bottom = top + height
        confidence = _tsv_confidence(columns[10], row_number)
        word = _ParsedWord(
            text=token_text,
            pixel_bounding_box=(
                float(left),
                float(top),
                float(right),
                float(bottom),
            ),
            confidence=confidence,
            line_key=line_key,
        )
        grouped.setdefault(word.line_key, []).append(word)
        word_count += 1
        text_characters += len(token_text)
        if word_count > configuration.max_tokens_per_selection:
            raise OCRContractLimitError(
                "TSV token count exceeds max_tokens_per_selection"
            )
        if text_characters > configuration.max_text_characters_per_selection:
            raise OCRContractLimitError(
                "TSV text exceeds max_text_characters_per_selection"
            )
    if len(grouped) > configuration.max_lines_per_selection:
        raise OCRContractLimitError(
            "TSV line count exceeds max_lines_per_selection"
        )
    parsed_lines: list[_ParsedLine] = []
    line_text_characters = 0
    for words in grouped.values():
        line_text = " ".join(word.text for word in words)
        line_text_characters += len(line_text)
        x0 = min(word.pixel_bounding_box[0] for word in words)
        y0 = min(word.pixel_bounding_box[1] for word in words)
        x1 = max(word.pixel_bounding_box[2] for word in words)
        y1 = max(word.pixel_bounding_box[3] for word in words)
        confidences = tuple(word.confidence for word in words)
        line_confidence = (
            sum(value for value in confidences if value is not None)
            / len(confidences)
            if all(value is not None for value in confidences)
            else None
        )
        parsed_lines.append(
            _ParsedLine(
                text=line_text,
                pixel_bounding_box=(x0, y0, x1, y1),
                confidence=line_confidence,
                words=tuple(words),
            )
        )
    retained_text_characters = 0
    if configuration.output_mode in (
        OCROutputMode.TOKENS,
        OCROutputMode.TOKENS_AND_LINES,
    ):
        retained_text_characters += text_characters
    if configuration.output_mode in (
        OCROutputMode.LINES,
        OCROutputMode.TOKENS_AND_LINES,
    ):
        retained_text_characters += line_text_characters
    if retained_text_characters > (
        configuration.max_text_characters_per_selection
    ):
        raise OCRContractLimitError(
            "TSV text exceeds max_text_characters_per_selection"
        )
    return tuple(parsed_lines)


def _run_bounded(
    command: tuple[str, ...],
    *,
    cwd: Path | None,
    environment: dict[str, str],
    timeout_milliseconds: int,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> _ProcessCapture:
    if os.name != "posix":  # pragma: no cover - platform-specific guard
        return _ProcessCapture(
            returncode=127,
            stdout=b"",
            stderr=b"POSIX subprocess isolation is unavailable",
        )
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as error:
        return _ProcessCapture(
            returncode=127,
            stdout=b"",
            stderr=str(error).encode("utf-8", errors="replace"),
        )
    if process.stdout is None or process.stderr is None:
        _kill_process_group(process)
        process.wait()
        raise RuntimeError("subprocess capture pipes were not created")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": max_stdout_bytes, "stderr": max_stderr_bytes}
    exceeded = {"stdout": False, "stderr": False}
    timed_out = False
    killed = False
    deadline = time.monotonic() + timeout_milliseconds / 1_000.0
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                timed_out = True
                _kill_process_group(process)
                killed = True
                break
            events = selector.select(timeout=min(remaining, 0.05))
            for key, _ in events:
                stream_name = str(key.data)
                chunk = os.read(key.fd, _READ_CHUNK_BYTES)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer = buffers[stream_name]
                limit = limits[stream_name]
                available = max(0, limit + 1 - len(buffer))
                if available:
                    buffer.extend(chunk[:available])
                if len(buffer) > limit or len(chunk) > available:
                    exceeded[stream_name] = True
                    _kill_process_group(process)
                    killed = True
                    break
            if killed:
                break
        if killed:
            try:
                process.wait(timeout=1.0)
            except (
                subprocess.TimeoutExpired
            ):  # pragma: no cover - SIGKILL guard
                process.kill()
                process.wait()
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                timed_out = True
                _kill_process_group(process)
                process.wait()
            else:
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _kill_process_group(process)
                    process.wait()
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    return _ProcessCapture(
        returncode=int(process.returncode),
        stdout=bytes(buffers["stdout"][:max_stdout_bytes]),
        stderr=bytes(buffers["stderr"][:max_stderr_bytes]),
        timed_out=timed_out,
        stdout_limit_exceeded=exceeded["stdout"],
        stderr_limit_exceeded=exceeded["stderr"],
    )


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:  # pragma: no cover - defensive platform fallback
        process.kill()


def _parse_tesseract_version(capture: _ProcessCapture) -> str:
    if (
        capture.returncode != 0
        or capture.timed_out
        or capture.stdout_limit_exceeded
        or capture.stderr_limit_exceeded
    ):
        return "unavailable"
    combined = capture.stdout + b"\n" + capture.stderr
    text = combined.decode("utf-8", errors="replace")
    normalized = "\n".join(
        " ".join(line.split()) for line in text.splitlines() if line.strip()
    )
    for line in normalized.splitlines():
        match = re.match(r"^tesseract\s+v?([^\s]+)", line, re.I)
        if match:
            version = match.group(1)
            if 0 < len(version) <= 128:
                report_digest = hashlib.sha256(
                    normalized.encode("utf-8")
                ).hexdigest()
                return (
                    f"{version}+version-output-sha256:{report_digest}"
                )
    return "unavailable"


def _resolve_executable(value: str) -> Path | None:
    candidate: str | None
    if os.sep in value or (os.altsep is not None and os.altsep in value):
        candidate = value
    else:
        candidate = shutil.which(value)
    if candidate is None:
        return None
    path = Path(candidate).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        return None
    return path


def _base_environment(temporary_path: Path | None) -> dict[str, str]:
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "OMP_NUM_THREADS": "1",
        "OMP_THREAD_LIMIT": "1",
        "PATH": os.defpath,
    }
    if temporary_path is not None:
        environment["HOME"] = str(temporary_path)
        environment["TMPDIR"] = str(temporary_path)
    return environment


def _hash_bounded_file(
    path: Path, maximum_bytes: int
) -> tuple[str | None, int, str | None]:
    digest = hashlib.sha256()
    size = 0
    try:
        reader, declared_size = _open_regular_file(path)
        with reader:
            if declared_size > maximum_bytes:
                return None, declared_size, "resource-size-limit"
            while True:
                chunk = reader.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > maximum_bytes:
                    return None, size, "resource-size-limit"
                digest.update(chunk)
    except FileNotFoundError:
        return None, 0, "resource-missing"
    except OSError:
        return None, 0, "resource-unreadable"
    return digest.hexdigest(), size, None


def _copy_bounded_file(
    source: Path, destination: Path, maximum_bytes: int
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    reader, declared_size = _open_regular_file(source)
    with reader:
        if declared_size > maximum_bytes:
            raise OCRContractLimitError(
                "language resource exceeds adapter limits"
            )
        with destination.open("xb") as writer:
            while True:
                chunk = reader.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > maximum_bytes:
                    raise OCRContractLimitError(
                        "language resource exceeds adapter limits"
                    )
                digest.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    return digest.hexdigest(), size


def _open_regular_file(path: Path) -> tuple[BinaryIO, int]:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise OSError("language resource must be a regular file")
        return os.fdopen(descriptor, "rb"), int(file_stat.st_size)
    except BaseException:
        os.close(descriptor)
        raise


def _write_exclusive(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _inspection_issue(
    inspection: _BackendInspection,
    *,
    kind: OCRFailureKind,
    code: str,
    message: str,
    retryable: bool = False,
) -> _BackendInspection:
    return _BackendInspection(
        executable=inspection.executable,
        executable_sha256=inspection.executable_sha256,
        backend_version=inspection.backend_version,
        language_resources=inspection.language_resources,
        binding_by_language=inspection.binding_by_language,
        issue_kind=kind,
        issue_code=code,
        issue_message=message,
        issue_retryable=retryable,
    )


def _identity_keywords(identity: OCRProcessorIdentity) -> _IdentityKeywords:
    return {
        "processor_name": identity.processor_name,
        "processor_version": identity.processor_version,
        "backend_name": identity.backend_name,
        "backend_version": identity.backend_version,
    }


def _word_confidence(value: float | None) -> OCRConfidence | None:
    if value is None:
        return None
    return OCRConfidence(
        value=value,
        method="tesseract-tsv-word-confidence",
        method_version="1",
        scale="tesseract_0_to_100_normalized_to_unit_interval",
    )


def _line_confidence(value: float | None) -> OCRConfidence | None:
    if value is None:
        return None
    return OCRConfidence(
        value=value,
        method="tesseract-tsv-line-mean-word-confidence",
        method_version="1",
        scale="arithmetic_mean_of_normalized_word_scores",
    )


def _tsv_integer(value: str, row_number: int) -> int:
    if not re.fullmatch(r"-?\d+", value):
        raise ValueError(f"TSV row {row_number} contains a non-integer field")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"TSV row {row_number} contains a negative field")
    return parsed


def _tsv_confidence(value: str, row_number: int) -> float | None:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(
            f"TSV row {row_number} has invalid confidence"
        ) from error
    if not math.isfinite(parsed):
        raise ValueError(f"TSV row {row_number} has invalid confidence")
    if parsed == -1.0:
        return None
    if not 0.0 <= parsed <= 100.0:
        raise ValueError(f"TSV row {row_number} has invalid confidence")
    normalized = parsed / 100.0
    return 0.0 if normalized == 0.0 else normalized


def _bounded_reason(error: BaseException) -> str:
    return " ".join(str(error).split())[:2_000]


def _unique_in_order(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError("resource names must be strings")
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def _bounded_identity_string(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or len(value) > _MAX_IDENTITY_CHARACTERS:
        raise TesseractAdapterConfigurationError(
            f"{name} must contain 1 to {_MAX_IDENTITY_CHARACTERS} characters"
        )
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise TesseractAdapterConfigurationError(
            f"{name} must be valid UTF-8"
        ) from error


def _positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TesseractAdapterConfigurationError(
            f"{name} must be a positive integer"
        )


def _nonnegative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TesseractAdapterConfigurationError(
            f"{name} must be a non-negative integer"
        )
