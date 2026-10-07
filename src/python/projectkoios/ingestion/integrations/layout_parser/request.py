"""Immutable request to adapt frozen LayoutParser detections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.request import (
    ConfigurableDataObjectActionRequest,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.layout_parser.configuration import (
    LayoutParserProposalConfiguration,
)
from projectkoios.ingestion.integrations.layout_parser.detection import (
    LayoutParserDetection,
)
from projectkoios.ingestion.layout.proposal.limits.error import (
    LayoutProposalLimitError,
)
from projectkoios.ingestion.layout.render.evidence import (
    LayoutPageRenderEvidence,
)

from .limits.definition import (
    MAX_LAYOUT_PARSER_DETECTION_LABEL_CHARACTERS,
)
from .limits.error import LayoutParserLimitError


@dataclass(frozen=True, slots=True)
class LayoutParserProposalRequest(
    ConfigurableDataObjectActionRequest[LayoutParserProposalConfiguration]
):
    """Bind exact pixels, frozen detections, and the producing resource."""

    CONTRACT_NAME: ClassVar[str] = "layout-parser-proposal-request"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    request_id: str
    render: LayoutPageRenderEvidence
    detections: tuple[LayoutParserDetection, ...]
    configuration: LayoutParserProposalConfiguration
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        render: LayoutPageRenderEvidence,
        detections: tuple[LayoutParserDetection, ...],
        configuration: LayoutParserProposalConfiguration,
    ) -> LayoutParserProposalRequest:
        """Create one complete frozen-detection adaptation request."""
        cls.validate(
            render=render,
            detections=detections,
            configuration=configuration,
        )
        request_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            render.render_id,
            tuple(detection.detection_id for detection in detections),
            configuration.configuration_id,
        )
        return cls(
            request_id=request_id,
            render=render,
            detections=detections,
            configuration=configuration,
        )

    @classmethod
    def validate(
        cls,
        *,
        render: LayoutPageRenderEvidence,
        detections: tuple[LayoutParserDetection, ...],
        configuration: LayoutParserProposalConfiguration,
    ) -> None:
        """Validate exact render identity, labels, bounds, and count limits."""
        if type(render) is not LayoutPageRenderEvidence:
            raise TypeError("render must be LayoutPageRenderEvidence")
        if type(configuration) is not LayoutParserProposalConfiguration:
            raise TypeError(
                "configuration must be LayoutParserProposalConfiguration"
            )
        if not isinstance(detections, tuple):
            raise TypeError("detections must be a tuple")
        if len(detections) > configuration.max_detections:
            raise LayoutProposalLimitError("detections exceed max_detections")
        supported_labels = {label for label, _ in configuration.label_mapping}
        detection_ids: set[str] = set()
        detection_label_characters = 0
        for detection in detections:
            if type(detection) is not LayoutParserDetection:
                raise TypeError("detections must contain LayoutParserDetection")
            if detection.detection_id in detection_ids:
                raise ValueError("detection IDs must be unique")
            detection_ids.add(detection.detection_id)
            if detection.render_id != render.render_id:
                raise ValueError("detection identifies another render")
            if detection.label not in supported_labels:
                raise ValueError("detection label is not mapped")
            detection_label_characters += len(detection.label)
            if (
                detection_label_characters
                > MAX_LAYOUT_PARSER_DETECTION_LABEL_CHARACTERS
            ):
                raise LayoutParserLimitError(
                    "detection labels exceed aggregate character limit"
                )
            x1, y1, x2, y2 = detection.bounding_box_pixels
            if (
                x1 < 0.0
                or y1 < 0.0
                or x2 > render.image_width
                or y2 > render.image_height
            ):
                raise ValueError("detection bounding box exceeds render bounds")

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported LayoutParser proposal request contract"
            )
        self.validate(
            render=self.render,
            detections=self.detections,
            configuration=self.configuration,
        )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.render.render_id,
            tuple(detection.detection_id for detection in self.detections),
            self.configuration.configuration_id,
        )
        if self.request_id != expected:
            raise ValueError("LayoutParser proposal request ID is inconsistent")
