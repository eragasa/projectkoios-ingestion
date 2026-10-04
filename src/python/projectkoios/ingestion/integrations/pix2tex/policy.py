"""Deterministic Pix2Tex primary-recognition gate."""

from __future__ import annotations

import zlib

from projectkoios.ingestion.equations.assembly.model import EquationAssembly
from projectkoios.ingestion.equations.recognition.policy import (
    primary_equation_recognition_ineligibility_reasons,
)


def pix2tex_primary_recognition_ineligibility_reasons(
    assembly: EquationAssembly,
) -> tuple[str, ...]:
    """Return deterministic reasons Pix2Tex invocation is ineligible."""

    reasons = list(
        primary_equation_recognition_ineligibility_reasons(assembly)
    )
    raw_text = " ".join(assembly.raw_fragments)
    if not 4 <= len(raw_text) <= 64:
        reasons.append("native_text_length_outside_4_64")
    if len(raw_text.split()) > 14:
        reasons.append("native_word_count_exceeds_14")
    if len(assembly.candidate_ids) > 3:
        reasons.append("grouped_candidate_count_exceeds_3")
    try:
        band_count, top_margin, bottom_margin = _foreground_profile(
            assembly.rendered_region.content
        )
    except ValueError:
        reasons.append("rendered_region_not_supported_rgb_png")
    else:
        if band_count > 2:
            reasons.append("foreground_band_count_exceeds_2")
        if band_count == 2 and (
            top_margin < 0.02 or bottom_margin < 0.02
        ):
            reasons.append("two_band_region_touches_vertical_edge")
    return tuple(reasons)


def is_pix2tex_primary_recognition_candidate(
    assembly: EquationAssembly,
) -> bool:
    """Return whether an assembly is eligible for Pix2Tex invocation."""

    return not pix2tex_primary_recognition_ineligibility_reasons(assembly)


def _foreground_profile(content: bytes) -> tuple[int, float, float]:
    """Return bounded foreground-band evidence from an opaque RGB PNG."""

    if len(content) < 45 or content[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("rendered region is not PNG")
    offset = 8
    width = 0
    height = 0
    compressed = bytearray()
    while offset + 12 <= len(content):
        length = int.from_bytes(content[offset : offset + 4], "big")
        chunk_type = content[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        chunk_end = data_end + 4
        if chunk_end > len(content):
            raise ValueError("PNG chunk exceeds content")
        data = content[data_start:data_end]
        if chunk_type == b"IHDR":
            if (
                length != 13
                or data[8] != 8
                or data[9] != 2
                or data[10:] != b"\x00\x00\x00"
            ):
                raise ValueError("PNG must be non-interlaced 8-bit RGB")
            width = int.from_bytes(data[:4], "big")
            height = int.from_bytes(data[4:8], "big")
        elif chunk_type == b"IDAT":
            compressed.extend(data)
        elif chunk_type == b"IEND":
            break
        offset = chunk_end
    if width <= 0 or height <= 0 or not compressed:
        raise ValueError("PNG structure is incomplete")
    stride = width * 3
    try:
        filtered = zlib.decompress(bytes(compressed))
    except zlib.error as error:
        raise ValueError("PNG image data is invalid") from error
    if len(filtered) != height * (stride + 1):
        raise ValueError("PNG image data has unexpected dimensions")
    previous = bytearray(stride)
    active_rows: list[int] = []
    band_count = 0
    inside_band = False
    minimum_ink = max(2, int(width * 0.002))
    for row_index in range(height):
        start = row_index * (stride + 1)
        filter_type = filtered[start]
        source = filtered[start + 1 : start + 1 + stride]
        row = bytearray(stride)
        for index, value in enumerate(source):
            left = row[index - 3] if index >= 3 else 0
            above = previous[index]
            upper_left = previous[index - 3] if index >= 3 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - upper_left
                left_distance = abs(estimate - left)
                above_distance = abs(estimate - above)
                upper_left_distance = abs(estimate - upper_left)
                if (
                    left_distance <= above_distance
                    and left_distance <= upper_left_distance
                ):
                    predictor = left
                elif above_distance <= upper_left_distance:
                    predictor = above
                else:
                    predictor = upper_left
            else:
                raise ValueError("PNG uses an unsupported row filter")
            row[index] = (value + predictor) & 0xFF
        ink_count = sum(
            min(row[index : index + 3]) < 180
            for index in range(0, stride, 3)
        )
        active = ink_count >= minimum_ink
        if active and not inside_band:
            band_count += 1
        if active:
            active_rows.append(row_index)
        inside_band = active
        previous = row
    if not active_rows:
        raise ValueError("PNG has no bounded foreground evidence")
    return (
        band_count,
        min(active_rows) / height,
        (height - 1 - max(active_rows)) / height,
    )
