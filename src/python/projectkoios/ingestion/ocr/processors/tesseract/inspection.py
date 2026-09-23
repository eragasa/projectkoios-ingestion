from __future__ import annotations

from pathlib import Path

from projectkoios.ingestion.ocr.models import (
    OCRContractLimitError,
    OCRFailureKind,
    OCRLanguageResourceIdentity,
    OcrProcessorIdentity,
    OcrRequest,
    OCRResourceIdentityKind,
)
from projectkoios.ingestion.ocr.processors.tesseract.constants import (
    MAX_EXECUTABLE_BYTES,
    TESSERACT_BACKEND_NAME,
    VERSION_CAPTURE_BYTES,
)
from projectkoios.ingestion.ocr.processors.tesseract.identity import (
    TesseractIdentity,
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


class TesseractBackendInspector:
    def __init__(
        self,
        *,
        processor_name: str,
        processor_version: str,
        executable: str,
        configuration: TesseractAdapterConfiguration,
        language_bindings: tuple[TesseractLanguageBinding, ...],
        runner: TesseractRunner,
        resources: TesseractResourceManager,
    ) -> None:
        self.name = processor_name
        self.version = processor_version
        self.executable = executable
        self.configuration = configuration
        self.language_bindings = language_bindings
        self.runner = runner
        self.resources = resources

    def inspect(self, request: OcrRequest) -> BackendInspection:
        if not isinstance(request, OcrRequest):
            raise TypeError("request must be an OcrRequest")
        executable = self.runner.resolve_executable(self.executable)
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
            version_capture = self.runner.run(
                (str(executable), "--version"),
                cwd=None,
                environment=self.runner.base_environment(None),
                timeout_milliseconds=5_000,
                max_stdout_bytes=VERSION_CAPTURE_BYTES,
                max_stderr_bytes=VERSION_CAPTURE_BYTES,
            )
            backend_version = TesseractIdentity.parse_version(version_capture)
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
                ) = self.resources.hash_bounded_file(
                    executable, MAX_EXECUTABLE_BYTES
                )
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
                        f"{backend_version}+binary-sha256:{executable_sha256}"
                    )

        by_language = {
            binding.language: binding for binding in self.language_bindings
        }
        identities: list[OCRLanguageResourceIdentity] = []
        requested_bindings: list[tuple[str, TesseractLanguageBinding]] = []
        resource_by_name: dict[str, tuple[str | None, int, str | None]] = {}
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
                    digest, size, resource_issue = (
                        self.resources.hash_bounded_file(
                            binding.traineddata_path,
                            read_limit,
                        )
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
        return BackendInspection(
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

    def processor_identity(
        self, inspection: BackendInspection
    ) -> OcrProcessorIdentity:
        return OcrProcessorIdentity(
            processor_name=self.name,
            processor_version=self.version,
            backend_name=TESSERACT_BACKEND_NAME,
            backend_version=inspection.backend_version,
            language_resources=inspection.language_resources,
        )

    def stage_resources(
        self,
        inspection: BackendInspection,
        destination: Path,
    ) -> BackendInspection | None:
        if (
            inspection.executable is None
            or inspection.executable_sha256 is None
        ):
            raise RuntimeError("usable inspection has no executable identity")
        executable_digest, _, executable_issue = (
            self.resources.hash_bounded_file(
                inspection.executable, MAX_EXECUTABLE_BYTES
            )
        )
        if executable_issue == "resource-size-limit":
            return TesseractIdentity.inspection_issue(
                inspection,
                kind=OCRFailureKind.RESOURCE_LIMIT,
                code="ocr.tesseract.executable_limit",
                message="Tesseract executable exceeds adapter limits",
            )
        if (
            executable_issue is not None
            or executable_digest != inspection.executable_sha256
        ):
            return TesseractIdentity.inspection_issue(
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
                return TesseractIdentity.inspection_issue(
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
                digest, size = self.resources.copy_bounded_file(
                    binding.traineddata_path,
                    target,
                    self.configuration.max_resource_bytes,
                )
            except OCRContractLimitError:
                return TesseractIdentity.inspection_issue(
                    inspection,
                    kind=OCRFailureKind.RESOURCE_LIMIT,
                    code="ocr.tesseract.resource_limit",
                    message=(
                        "Tesseract language resources exceed adapter limits"
                    ),
                )
            except OSError:
                return TesseractIdentity.inspection_issue(
                    inspection,
                    kind=OCRFailureKind.PROCESSOR_UNAVAILABLE,
                    code="ocr.tesseract.resource_unavailable",
                    message=(
                        "A requested Tesseract language resource is unavailable"
                    ),
                )
            total += size
            if total > self.configuration.max_total_resource_bytes:
                return TesseractIdentity.inspection_issue(
                    inspection,
                    kind=OCRFailureKind.RESOURCE_LIMIT,
                    code="ocr.tesseract.resource_limit",
                    message=(
                        "Tesseract language resources exceed adapter limits"
                    ),
                )
            if digest != expected_by_name[resource_name]:
                return TesseractIdentity.inspection_issue(
                    inspection,
                    kind=OCRFailureKind.PROCESSOR_UNAVAILABLE,
                    code="ocr.tesseract.resource_changed",
                    message=(
                        "A Tesseract language resource changed before execution"
                    ),
                    retryable=True,
                )
        return None


__all__ = ["TesseractBackendInspector"]
