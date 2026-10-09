"""Runtime-neutral image preprocessing evidence for local detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


class CocoLayoutDetectorImageMode(StrEnum):
    """Closed image color modes accepted by detector preprocessing."""

    RGB = "RGB"


class CocoLayoutDetectorResampling(StrEnum):
    """Closed geometric resampling vocabulary."""

    BILINEAR = "bilinear"


class CocoLayoutDetectorTensorDataType(StrEnum):
    """Closed detector tensor data types."""

    UINT8 = "uint8"


class CocoLayoutDetectorTensorLayout(StrEnum):
    """Closed detector tensor dimension layouts."""

    NCHW = "NCHW"


class CocoLayoutDetectorOriginalSizeOrder(StrEnum):
    """Closed original-image size argument order."""

    WIDTH_HEIGHT = "width_height"


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorPreprocessing(AbstractImmutableDataObject):
    """Pin every image-to-detector tensor transformation choice."""

    target_width: int
    target_height: int
    image_mode: CocoLayoutDetectorImageMode
    resampling: CocoLayoutDetectorResampling
    tensor_data_type: CocoLayoutDetectorTensorDataType
    tensor_layout: CocoLayoutDetectorTensorLayout
    original_size_order: CocoLayoutDetectorOriginalSizeOrder
    preprocessing_id: str = field(init=False)

    def __post_init__(self) -> None:
        width = LayoutValueValidation.require_positive_integer(
            "target_width", self.target_width, maximum=16_384
        )
        height = LayoutValueValidation.require_positive_integer(
            "target_height", self.target_height, maximum=16_384
        )
        enum_values = (
            (self.image_mode, CocoLayoutDetectorImageMode, "image_mode"),
            (self.resampling, CocoLayoutDetectorResampling, "resampling"),
            (
                self.tensor_data_type,
                CocoLayoutDetectorTensorDataType,
                "tensor_data_type",
            ),
            (
                self.tensor_layout,
                CocoLayoutDetectorTensorLayout,
                "tensor_layout",
            ),
            (
                self.original_size_order,
                CocoLayoutDetectorOriginalSizeOrder,
                "original_size_order",
            ),
        )
        for value, enum_type, name in enum_values:
            if not isinstance(value, enum_type):
                raise TypeError(f"{name} must use its closed enum")
        object.__setattr__(
            self,
            "preprocessing_id",
            stable_id(
                "coco-layout-detector-preprocessing",
                width,
                height,
                self.image_mode,
                self.resampling,
                self.tensor_data_type,
                self.tensor_layout,
                self.original_size_order,
            ),
        )

    @classmethod
    def docling_heron_onnx_v0_1(cls) -> CocoLayoutDetectorPreprocessing:
        """Return the exact preprocessing used by the pinned Heron export."""
        return cls(
            target_width=640,
            target_height=640,
            image_mode=CocoLayoutDetectorImageMode.RGB,
            resampling=CocoLayoutDetectorResampling.BILINEAR,
            tensor_data_type=CocoLayoutDetectorTensorDataType.UINT8,
            tensor_layout=CocoLayoutDetectorTensorLayout.NCHW,
            original_size_order=(
                CocoLayoutDetectorOriginalSizeOrder.WIDTH_HEIGHT
            ),
        )
