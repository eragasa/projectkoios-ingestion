"""Exact affine mapping between rendered pixels and source-page geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.render.limits.definition import (
    MAX_LAYOUT_RENDER_DIMENSION_PIXELS,
    MAX_LAYOUT_RENDER_PIXELS,
)
from projectkoios.ingestion.layout.render.limits.error import (
    LayoutRenderLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

LayoutAffineMatrix = tuple[float, float, float, float, float, float]
LayoutBoundingBox = tuple[float, float, float, float]
LAYOUT_PIXEL_COORDINATE_SYSTEM = "raster_pixel_edges_top_left"


@dataclass(frozen=True, slots=True)
class LayoutPixelMapping(AbstractImmutableDataObject):
    """Retain one exact quarter-turn affine source/pixel mapping."""

    CONTRACT_NAME: ClassVar[str] = "layout-pixel-mapping"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    mapping_id: str
    source_coordinate_system: str
    pixel_coordinate_system: str
    requested_source_bounding_box: LayoutBoundingBox
    effective_source_bounding_box: LayoutBoundingBox
    pixel_to_source_matrix: LayoutAffineMatrix
    pixel_rounding: str
    page_rotation_degrees: int
    image_width: int
    image_height: int
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        source_coordinate_system: str,
        requested_source_bounding_box: LayoutBoundingBox,
        effective_source_bounding_box: LayoutBoundingBox,
        pixel_to_source_matrix: LayoutAffineMatrix,
        pixel_rounding: str,
        page_rotation_degrees: int,
        image_width: int,
        image_height: int,
        pixel_coordinate_system: str = LAYOUT_PIXEL_COORDINATE_SYSTEM,
    ) -> LayoutPixelMapping:
        """Create one bounded mapping after validating all geometry."""
        values = cls.normalized_values(
            source_coordinate_system=source_coordinate_system,
            pixel_coordinate_system=pixel_coordinate_system,
            requested_source_bounding_box=requested_source_bounding_box,
            effective_source_bounding_box=effective_source_bounding_box,
            pixel_to_source_matrix=pixel_to_source_matrix,
            pixel_rounding=pixel_rounding,
            page_rotation_degrees=page_rotation_degrees,
            image_width=image_width,
            image_height=image_height,
        )
        mapping_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            *values,
        )
        return cls(
            mapping_id=mapping_id,
            source_coordinate_system=values[0],
            pixel_coordinate_system=values[1],
            requested_source_bounding_box=values[2],
            effective_source_bounding_box=values[3],
            pixel_to_source_matrix=values[4],
            pixel_rounding=values[5],
            page_rotation_degrees=values[6],
            image_width=values[7],
            image_height=values[8],
        )

    @classmethod
    def normalized_values(
        cls,
        *,
        source_coordinate_system: object,
        pixel_coordinate_system: object,
        requested_source_bounding_box: object,
        effective_source_bounding_box: object,
        pixel_to_source_matrix: object,
        pixel_rounding: object,
        page_rotation_degrees: object,
        image_width: object,
        image_height: object,
    ) -> tuple[
        str,
        str,
        LayoutBoundingBox,
        LayoutBoundingBox,
        LayoutAffineMatrix,
        str,
        int,
        int,
        int,
    ]:
        """Normalize and cross-check every persisted mapping value."""
        source_system = LayoutValueValidation.require_text(
            "source_coordinate_system", source_coordinate_system
        )
        pixel_system = LayoutValueValidation.require_text(
            "pixel_coordinate_system", pixel_coordinate_system
        )
        if pixel_system != LAYOUT_PIXEL_COORDINATE_SYSTEM:
            raise ValueError("unsupported layout pixel coordinate system")
        requested_box = LayoutValueValidation.require_box(
            "requested_source_bounding_box", requested_source_bounding_box
        )
        effective_box = LayoutValueValidation.require_box(
            "effective_source_bounding_box", effective_source_bounding_box
        )
        matrix = cls.normalize_matrix(pixel_to_source_matrix)
        rounding = LayoutValueValidation.require_text(
            "pixel_rounding", pixel_rounding
        )
        rotation = LayoutValueValidation.require_nonnegative_integer(
            "page_rotation_degrees", page_rotation_degrees
        )
        if rotation not in (0, 90, 180, 270):
            raise ValueError("page_rotation_degrees must be a quarter turn")
        width = LayoutValueValidation.require_positive_integer(
            "image_width", image_width
        )
        height = LayoutValueValidation.require_positive_integer(
            "image_height", image_height
        )
        if (
            width > MAX_LAYOUT_RENDER_DIMENSION_PIXELS
            or height > MAX_LAYOUT_RENDER_DIMENSION_PIXELS
        ):
            raise LayoutRenderLimitError(
                "render dimension exceeds implementation maximum"
            )
        if width * height > MAX_LAYOUT_RENDER_PIXELS:
            raise LayoutRenderLimitError(
                "render pixel area exceeds implementation maximum"
            )
        cls.validate_quarter_turn(matrix=matrix, rotation=rotation)
        expected_effective_box = cls.effective_bounds_for(
            matrix=matrix,
            image_width=width,
            image_height=height,
        )
        if effective_box != expected_effective_box:
            raise ValueError(
                "effective source bounds differ from the affine mapping"
            )
        return (
            source_system,
            pixel_system,
            requested_box,
            effective_box,
            matrix,
            rounding,
            rotation,
            width,
            height,
        )

    @staticmethod
    def normalize_matrix(value: object) -> LayoutAffineMatrix:
        """Return six finite normalized affine coefficients."""
        if not isinstance(value, tuple) or len(value) != 6:
            raise ValueError("pixel_to_source_matrix must have six values")
        normalized = tuple(
            LayoutValueValidation.require_number(
                "pixel_to_source_matrix coefficient", coefficient
            )
            for coefficient in value
        )
        matrix = (
            normalized[0],
            normalized[1],
            normalized[2],
            normalized[3],
            normalized[4],
            normalized[5],
        )
        a, b, c, d, _, _ = matrix
        if a * d - b * c == 0.0:
            raise ValueError("pixel_to_source_matrix must be invertible")
        return matrix

    @staticmethod
    def validate_quarter_turn(
        *, matrix: LayoutAffineMatrix, rotation: int
    ) -> None:
        """Reject shear, reflection, and rotation inconsistent with metadata."""
        a, b, c, d, _, _ = matrix
        if rotation == 0:
            valid = a > 0.0 and d > 0.0 and b == 0.0 and c == 0.0
        elif rotation == 90:
            valid = a == 0.0 and d == 0.0 and b < 0.0 and c > 0.0
        elif rotation == 180:
            valid = a < 0.0 and d < 0.0 and b == 0.0 and c == 0.0
        else:
            valid = a == 0.0 and d == 0.0 and b > 0.0 and c < 0.0
        if not valid:
            raise ValueError(
                "pixel_to_source_matrix is not the declared quarter turn"
            )

    @staticmethod
    def effective_bounds_for(
        *,
        matrix: LayoutAffineMatrix,
        image_width: int,
        image_height: int,
    ) -> LayoutBoundingBox:
        """Return the normalized source envelope of all raster-edge corners."""
        a, b, c, d, e, f = matrix
        corners = (
            (e, f),
            (image_width * a + e, image_width * b + f),
            (image_height * c + e, image_height * d + f),
            (
                image_width * a + image_height * c + e,
                image_width * b + image_height * d + f,
            ),
        )
        xs = tuple(
            LayoutValueValidation.require_number("mapped source x", point[0])
            for point in corners
        )
        ys = tuple(
            LayoutValueValidation.require_number("mapped source y", point[1])
            for point in corners
        )
        return (min(xs), min(ys), max(xs), max(ys))

    def source_box_to_pixel_box(
        self, source_box: LayoutBoundingBox
    ) -> LayoutBoundingBox:
        """Map all source-box corners into exact raster-edge coordinates."""
        box = LayoutValueValidation.require_box("source_box", source_box)
        a, b, c, d, e, f = self.pixel_to_source_matrix
        determinant = a * d - b * c
        corners = (
            (box[0], box[1]),
            (box[2], box[1]),
            (box[0], box[3]),
            (box[2], box[3]),
        )
        pixel_points = tuple(
            (
                LayoutValueValidation.require_number(
                    "mapped pixel x",
                    (d * (x - e) - c * (y - f)) / determinant,
                ),
                LayoutValueValidation.require_number(
                    "mapped pixel y",
                    (-b * (x - e) + a * (y - f)) / determinant,
                ),
            )
            for x, y in corners
        )
        xs = tuple(point[0] for point in pixel_points)
        ys = tuple(point[1] for point in pixel_points)
        return LayoutValueValidation.require_box(
            "mapped pixel box",
            (min(xs), min(ys), max(xs), max(ys)),
        )

    def pixel_box_to_source_box(
        self, pixel_box: LayoutBoundingBox
    ) -> LayoutBoundingBox:
        """Map one bounded raster-edge box into source-page geometry."""
        box = LayoutValueValidation.require_box("pixel_box", pixel_box)
        if (
            box[0] < 0.0
            or box[1] < 0.0
            or box[2] > self.image_width
            or box[3] > self.image_height
        ):
            raise ValueError("pixel box exceeds mapped image bounds")
        a, b, c, d, e, f = self.pixel_to_source_matrix
        corners = (
            (box[0], box[1]),
            (box[2], box[1]),
            (box[0], box[3]),
            (box[2], box[3]),
        )
        source_points = tuple(
            (
                LayoutValueValidation.require_number(
                    "mapped source x", x * a + y * c + e
                ),
                LayoutValueValidation.require_number(
                    "mapped source y", x * b + y * d + f
                ),
            )
            for x, y in corners
        )
        xs = tuple(point[0] for point in source_points)
        ys = tuple(point[1] for point in source_points)
        return LayoutValueValidation.require_box(
            "mapped source box",
            (min(xs), min(ys), max(xs), max(ys)),
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout pixel mapping contract")
        values = self.normalized_values(
            source_coordinate_system=self.source_coordinate_system,
            pixel_coordinate_system=self.pixel_coordinate_system,
            requested_source_bounding_box=self.requested_source_bounding_box,
            effective_source_bounding_box=self.effective_source_bounding_box,
            pixel_to_source_matrix=self.pixel_to_source_matrix,
            pixel_rounding=self.pixel_rounding,
            page_rotation_degrees=self.page_rotation_degrees,
            image_width=self.image_width,
            image_height=self.image_height,
        )
        object.__setattr__(self, "requested_source_bounding_box", values[2])
        object.__setattr__(self, "effective_source_bounding_box", values[3])
        object.__setattr__(self, "pixel_to_source_matrix", values[4])
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            *values,
        )
        if self.mapping_id != expected:
            raise ValueError("layout pixel mapping ID is inconsistent")
