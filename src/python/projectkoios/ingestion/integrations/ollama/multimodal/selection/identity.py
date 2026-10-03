from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.identity import stable_id


@dataclass(frozen=True)
class OllamaMultimodalSelectionIdentity(AbstractIdentity):
    CONTRACT_NAME: ClassVar[str] = "ollama-multimodal-selection"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    selection_id: str
    source_id: str
    source_blob_id: str
    source_content_hash: str
    page_index: int
    region_id: str
    png_sha256: str
    png_byte_length: int
    width_pixels: int
    height_pixels: int

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_blob_id: str,
        source_content_hash: str,
        page_index: int,
        region_id: str,
        png_sha256: str,
        png_byte_length: int,
        width_pixels: int,
        height_pixels: int,
    ) -> OllamaMultimodalSelectionIdentity:
        return cls(
            selection_id=stable_id(
                cls.CONTRACT_NAME,
                cls.CONTRACT_VERSION,
                source_id,
                source_blob_id,
                source_content_hash,
                page_index,
                region_id,
                png_sha256,
                png_byte_length,
                width_pixels,
                height_pixels,
            ),
            source_id=source_id,
            source_blob_id=source_blob_id,
            source_content_hash=source_content_hash,
            page_index=page_index,
            region_id=region_id,
            png_sha256=png_sha256,
            png_byte_length=png_byte_length,
            width_pixels=width_pixels,
            height_pixels=height_pixels,
        )

    def __post_init__(self) -> None:
        self._validate_text("source_id", self.source_id, 4_096)
        self._validate_text("source_blob_id", self.source_blob_id, 4_096)
        self._validate_sha256("source content", self.source_content_hash)
        if self.source_blob_id != f"blob:sha256:{self.source_content_hash}":
            raise ValueError("selection blob and source hash disagree")
        self._validate_nonnegative("page_index", self.page_index)
        self._validate_text("region_id", self.region_id, 4_096)
        self._validate_sha256("PNG", self.png_sha256)
        self._validate_nonnegative("PNG byte length", self.png_byte_length)
        self._validate_positive("width_pixels", self.width_pixels)
        self._validate_positive("height_pixels", self.height_pixels)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.source_id,
            self.source_blob_id,
            self.source_content_hash,
            self.page_index,
            self.region_id,
            self.png_sha256,
            self.png_byte_length,
            self.width_pixels,
            self.height_pixels,
        )
        if self.selection_id != expected:
            raise ValueError("selection identity mismatch")

    @staticmethod
    def _validate_sha256(name: str, value: str) -> None:
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{name} identity must be a SHA-256 digest")
        try:
            int(value, 16)
        except ValueError as error:
            raise ValueError(
                f"{name} identity must be a SHA-256 digest"
            ) from error
        if value != value.lower():
            raise ValueError(f"{name} identity must use lowercase hexadecimal")

    @staticmethod
    def _validate_text(name: str, value: str, maximum: int) -> None:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        try:
            length = len(value.encode("utf-8", errors="strict"))
        except UnicodeError as error:
            raise ValueError(f"{name} contains invalid Unicode") from error
        if (
            not value
            or length > maximum
            or any(
                ord(character) < 32 or 127 <= ord(character) <= 159
                for character in value
            )
        ):
            raise ValueError(
                f"{name} is empty, contains controls, or exceeds its bound"
            )

    @staticmethod
    def _validate_nonnegative(name: str, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    @staticmethod
    def _validate_positive(name: str, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
