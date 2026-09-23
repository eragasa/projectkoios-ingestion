from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from projectkoios.ingestion.ocr.models import (
    OCRFailureKind,
    OcrProcessorIdentity,
)
from projectkoios.ingestion.ocr.processors.tesseract.models import (
    BackendInspection,
    IdentityKeywords,
    ProcessCapture,
)


class TesseractIdentity:
    @staticmethod
    def parse_version(capture: ProcessCapture) -> str:
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
                    return f"{version}+version-output-sha256:{report_digest}"
        return "unavailable"

    @staticmethod
    def inspection_issue(
        inspection: BackendInspection,
        *,
        kind: OCRFailureKind,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> BackendInspection:
        return BackendInspection(
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

    @staticmethod
    def keywords(identity: OcrProcessorIdentity) -> IdentityKeywords:
        return {
            "processor_name": identity.processor_name,
            "processor_version": identity.processor_version,
            "backend_name": identity.backend_name,
            "backend_version": identity.backend_version,
        }

    @staticmethod
    def bounded_reason(error: BaseException) -> str:
        return " ".join(str(error).split())[:2_000]

    @staticmethod
    def unique_in_order(values: Iterable[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not isinstance(value, str):
                raise TypeError("resource names must be strings")
            if value not in seen:
                seen.add(value)
                ordered.append(value)
        return tuple(ordered)


__all__ = ["TesseractIdentity"]
