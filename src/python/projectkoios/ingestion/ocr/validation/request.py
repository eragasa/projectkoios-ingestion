"""Cross-object OCR request validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectkoios.ingestion.ocr.limit.error import OCRContractLimitError

if TYPE_CHECKING:
    from projectkoios.ingestion.ocr.configuration import OCRConfiguration
    from projectkoios.ingestion.ocr.selection import OCRSelection
from projectkoios.ingestion.ocr.validation import value as primitives


def _preflight_request(
    selections: tuple[OCRSelection, ...], configuration: OCRConfiguration
) -> None:
    from projectkoios.ingestion.ocr.selection import OCRSelection

    if not selections:
        raise ValueError("an OCR request requires at least one selection")
    if len(selections) > configuration.max_selections:
        raise OCRContractLimitError("selection count exceeds max_selections")
    if configuration.max_total_warnings < len(selections):
        raise OCRContractLimitError(
            "max_total_warnings must allow one failure warning per selection"
        )
    if any(not isinstance(item, OCRSelection) for item in selections):
        raise TypeError("request selections must be OCRSelection values")
    selection_ids = tuple(selection.selection_id for selection in selections)
    if len(set(selection_ids)) != len(selection_ids):
        raise ValueError("OCR selection IDs must be unique")
    image_by_id = {
        selection.image.image_id: selection.image for selection in selections
    }
    if len(image_by_id) > configuration.max_images:
        raise OCRContractLimitError("image count exceeds max_images")

    total_pixels = 0
    total_bytes = 0
    total_identity_characters = 0
    for selection in selections:
        region = selection.image.rendered_region
        identity_strings = (
            selection.selection_id,
            selection.image.image_id,
            region.region_id,
            region.source_id,
            region.source_blob_id,
            region.source_content_hash,
            region.content_sha256,
            region.coordinate_system,
            region.pixel_rounding,
            region.media_type,
            region.processor_name,
            region.processor_version,
            region.backend_name,
            region.backend_version,
            region.configuration_digest,
            *(
                (region.printed_page_label,)
                if region.printed_page_label is not None
                else ()
            ),
            *selection.native_text_block_ids,
        )
        for value in identity_strings:
            primitives._bounded_string(
                "OCR identity field",
                value,
                configuration.max_identity_field_characters,
                nonempty=True,
            )
            total_identity_characters += len(value)
            if (
                total_identity_characters
                > configuration.max_total_identity_characters
            ):
                raise OCRContractLimitError(
                    "identity characters exceed max_total_identity_characters"
                )
    for image in image_by_id.values():
        region = image.rendered_region
        pixels = region.width_pixels * region.height_pixels
        if pixels > configuration.max_pixels_per_image:
            raise OCRContractLimitError(
                "image pixels exceed max_pixels_per_image"
            )
        if region.byte_length > configuration.max_bytes_per_image:
            raise OCRContractLimitError(
                "image bytes exceed max_bytes_per_image"
            )
        total_pixels += pixels
        total_bytes += region.byte_length
    if total_pixels > configuration.max_total_pixels:
        raise OCRContractLimitError("image pixels exceed max_total_pixels")
    if total_bytes > configuration.max_total_image_bytes:
        raise OCRContractLimitError("image bytes exceed max_total_image_bytes")
