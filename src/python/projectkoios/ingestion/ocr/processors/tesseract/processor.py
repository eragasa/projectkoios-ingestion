from __future__ import annotations

import os
import tempfile
from pathlib import Path

from projectkoios.ingestion.models import WarningSeverity
from projectkoios.ingestion.ocr.models import (
    OCRContractLimitError,
    OCRFailure,
    OCRFailureKind,
    OcrProcessorIdentity,
    OcrRequest,
    OcrResult,
    OCRSelection,
    OCRSelectionResult,
    OCRSelectionStatus,
    OCRWarning,
)
from projectkoios.ingestion.ocr.processors.base import BaseOcrProcessor
from projectkoios.ingestion.ocr.processors.tesseract.base import (
    BaseTesseractModel,
)
from projectkoios.ingestion.ocr.processors.tesseract.constants import (
    MAX_BINDINGS,
    TESSERACT_ADAPTER_VERSION,
)
from projectkoios.ingestion.ocr.processors.tesseract.errors import (
    TesseractAdapterConfigurationError,
)
from projectkoios.ingestion.ocr.processors.tesseract.identity import (
    TesseractIdentity,
)
from projectkoios.ingestion.ocr.processors.tesseract.inspection import (
    TesseractBackendInspector,
)
from projectkoios.ingestion.ocr.processors.tesseract.models import (
    BackendInspection,
    TesseractAdapterConfiguration,
    TesseractLanguageBinding,
)
from projectkoios.ingestion.ocr.processors.tesseract.resources import (
    TesseractResourceManager,
)
from projectkoios.ingestion.ocr.processors.tesseract.runner import (
    TesseractRunner,
)
from projectkoios.ingestion.ocr.processors.tesseract.tsv import (
    TesseractTsvParser,
)


class TesseractOcrProcessor(BaseOcrProcessor, BaseTesseractModel):
    """Bounded subprocess adapter for explicit Tesseract OCR selections."""

    name = "tesseract-ocr-adapter"
    runner = TesseractRunner()
    resources = TesseractResourceManager()

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
        if len(language_bindings) > MAX_BINDINGS:
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
        self._bounded_identity_string("executable", executable_value)
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
        self.inspector = TesseractBackendInspector(
            processor_name=self.name,
            processor_version=self.version,
            executable=self.executable,
            configuration=self.configuration,
            language_bindings=self.language_bindings,
            runner=self.runner,
            resources=self.resources,
        )

    def identity_for(self, request: OcrRequest) -> OcrProcessorIdentity:
        """Resolve engine version and exact requested language resources."""
        inspection = self.inspector.inspect(request)
        return self.inspector.processor_identity(inspection)

    def process(self, request: OcrRequest) -> OcrResult:
        """Run bounded subprocesses and preserve mixed selection outcomes."""
        if not isinstance(request, OcrRequest):
            raise TypeError("request must be an OcrRequest")
        inspection = self.inspector.inspect(request)
        identity = self.inspector.processor_identity(inspection)
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
            staging_issue = self.inspector.stage_resources(
                inspection, tessdata_path
            )
            if staging_issue is not None:
                return self._failed_result_for_all(
                    request, identity, staging_issue
                )

            resource_names = TesseractIdentity.unique_in_order(
                binding.resource_name
                for _, binding in inspection.binding_by_language
            )
            selection_results: list[OCRSelectionResult] = []
            for index, selection in enumerate(request.selections):
                input_path = images_path / f"selection-{index:06d}.png"
                try:
                    self.resources.write_exclusive(
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
                if TesseractTsvParser.exceeds_aggregate_limits(
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
            return OcrResult.create(
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
            return OcrResult.create(
                request=request,
                selection_results=fallback,
                processor_identity=identity,
            )

    def _process_selection(
        self,
        *,
        selection: OCRSelection,
        request: OcrRequest,
        identity: OcrProcessorIdentity,
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
        capture = self.runner.run(
            tuple(command),
            cwd=temporary_path,
            environment=self.runner.base_environment(temporary_path),
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
            parsed_lines = TesseractTsvParser.parse(
                capture.stdout, request.configuration
            )
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
            tokens, lines = TesseractTsvParser.build_outputs(
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
                **TesseractIdentity.keywords(identity),
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
                evidence=(("reason", TesseractIdentity.bounded_reason(error)),),
            )
        except (TypeError, ValueError, UnicodeError) as error:
            if invocation_failure is not None:
                kind, code, message, retryable, evidence = invocation_failure
                parse_reason = TesseractIdentity.bounded_reason(error)
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
                evidence=(("reason", TesseractIdentity.bounded_reason(error)),),
            )

    def _failed_result_for_all(
        self,
        request: OcrRequest,
        identity: OcrProcessorIdentity,
        inspection: BackendInspection,
    ) -> OcrResult:
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
        return OcrResult.create(
            request=request,
            selection_results=selection_results,
            processor_identity=identity,
        )

    def _failed_selection(
        self,
        *,
        selection: OCRSelection,
        request: OcrRequest,
        identity: OcrProcessorIdentity,
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
                value[: request.configuration.max_warning_message_characters],
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
            **TesseractIdentity.keywords(identity),
        )


__all__ = ["TesseractOcrProcessor"]
