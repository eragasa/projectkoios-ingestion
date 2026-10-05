"""OCRSelection OCR domain object."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.models import ExtractedPage
from projectkoios.ingestion.ocr import _identity as identity
from projectkoios.ingestion.ocr import _primitives as primitives
from projectkoios.ingestion.ocr import _validation as validation
from projectkoios.ingestion.ocr._limits import (
    _MAX_IDENTITY_FIELD_CHARACTERS,
    _MAX_NATIVE_TEXT_REFERENCES,
    _MAX_TOTAL_IDENTITY_CHARACTERS,
)
from projectkoios.ingestion.ocr.constants import OCR_CONTRACT_VERSION
from projectkoios.ingestion.ocr.limit_error import OCRContractLimitError
from projectkoios.ingestion.ocr.native_text_block_reference import (
    OCRNativeTextBlockReference,
)
from projectkoios.ingestion.ocr.page_image import OCRPageImage


@dataclass(frozen=True)
class OCRSelection(AbstractImmutableDataObject):
    """One explicit OCR selection; native IDs are coexistence evidence only."""

    selection_id: str
    image: OCRPageImage
    native_text_blocks: tuple[OCRNativeTextBlockReference, ...] = ()
    contract_version: str = OCR_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        image: OCRPageImage,
        *,
        native_text_page: ExtractedPage | None = None,
        native_text_block_ids: tuple[str, ...] = (),
    ) -> OCRSelection:
        primitives._require_tuple(
            "native_text_block_ids", native_text_block_ids
        )
        if len(native_text_block_ids) > _MAX_NATIVE_TEXT_REFERENCES:
            raise OCRContractLimitError("too many native text block IDs")
        primitives._require_unique_strings(
            "native_text_block_ids",
            native_text_block_ids,
            string_limit=_MAX_IDENTITY_FIELD_CHARACTERS,
        )
        if bool(native_text_block_ids) != (native_text_page is not None):
            raise ValueError(
                "native text block IDs require their containing extracted page"
            )
        references: tuple[OCRNativeTextBlockReference, ...] = ()
        if native_text_page is not None:
            references = validation._native_text_references(
                image, native_text_page, native_text_block_ids
            )
        return cls(
            selection_id=identity._ocr_selection_id(image, references),
            image=image,
            native_text_blocks=references,
        )

    def __post_init__(self) -> None:
        if self.contract_version != OCR_CONTRACT_VERSION:
            raise ValueError("unsupported OCR selection contract version")
        if not isinstance(self.image, OCRPageImage):
            raise TypeError("image must be an OCRPageImage")
        primitives._require_tuple("native_text_blocks", self.native_text_blocks)
        if len(self.native_text_blocks) > _MAX_NATIVE_TEXT_REFERENCES:
            raise OCRContractLimitError("too many native text references")
        if any(
            not isinstance(reference, OCRNativeTextBlockReference)
            for reference in self.native_text_blocks
        ):
            raise TypeError(
                "native_text_blocks must contain source-backed references"
            )
        reference_characters = sum(
            len(value)
            for reference in self.native_text_blocks
            for value in (
                reference.block_id,
                reference.source_id,
                reference.source_blob_id,
            )
        )
        if reference_characters > _MAX_TOTAL_IDENTITY_CHARACTERS:
            raise OCRContractLimitError(
                "native text references exceed the identity safety limit"
            )
        block_ids = tuple(item.block_id for item in self.native_text_blocks)
        if len(set(block_ids)) != len(block_ids):
            raise ValueError("native text block IDs must be unique")
        region = self.image.rendered_region
        for reference in self.native_text_blocks:
            if not isinstance(reference, OCRNativeTextBlockReference):
                raise TypeError(
                    "native_text_blocks must contain source-backed references"
                )
            if (
                reference.source_id != region.source_id
                or reference.source_blob_id != region.source_blob_id
                or reference.page_index != region.page_index
            ):
                raise ValueError(
                    "native text evidence must refer to the rendered "
                    "source page"
                )
        expected = identity._ocr_selection_id(
            self.image, self.native_text_blocks
        )
        if self.selection_id != expected:
            raise ValueError("OCR selection ID does not match its evidence")

    @property
    def native_text_block_ids(self) -> tuple[str, ...]:
        return tuple(item.block_id for item in self.native_text_blocks)

    def identity_parts(self) -> tuple[object, ...]:
        return (
            self.image.identity_parts(),
            tuple(item.identity_parts() for item in self.native_text_blocks),
        )
