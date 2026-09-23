from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from projectkoios.ingestion.ocr.processors.tesseract.constants import (
    MAX_IDENTITY_CHARACTERS,
)
from projectkoios.ingestion.ocr.processors.tesseract.errors import (
    TesseractAdapterConfigurationError,
)

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.processors.tesseract.models import (
        ProcessCapture,
    )


class BaseTesseractModel:
    @staticmethod
    def _bounded_identity_string(name: str, value: object) -> None:
        if not isinstance(value, str) or not value:
            raise TesseractAdapterConfigurationError(
                f"{name} must be a non-empty string"
            )
        if len(value) > MAX_IDENTITY_CHARACTERS:
            raise TesseractAdapterConfigurationError(
                f"{name} exceeds the identity character limit"
            )
        if "\x00" in value:
            raise TesseractAdapterConfigurationError(
                f"{name} cannot contain a NUL character"
            )

    @staticmethod
    def _positive_integer(name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise TesseractAdapterConfigurationError(
                f"{name} must be a positive integer"
            )

    @staticmethod
    def _nonnegative_integer(name: str, value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TesseractAdapterConfigurationError(
                f"{name} must be a non-negative integer"
            )


class BaseTesseractRunner(ABC):
    @abstractmethod
    def run(
        self,
        command: tuple[str, ...],
        *,
        cwd: Path | None,
        environment: dict[str, str],
        timeout_milliseconds: int,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ) -> ProcessCapture:
        raise NotImplementedError


__all__ = ["BaseTesseractModel", "BaseTesseractRunner"]
