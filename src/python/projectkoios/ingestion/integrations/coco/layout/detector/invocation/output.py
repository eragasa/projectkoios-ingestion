"""Typed canonical raw output from a local detector provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detector.observation import (  # noqa: E501
    CocoLayoutDetectorObservation,
    CocoLayoutDetectorObservationInventory,
)
from projectkoios.ingestion.integrations.coco.layout.json.base import (
    CocoLayoutJsonContract,
)
from projectkoios.ingestion.integrations.coco.layout.json.value import (
    CocoLayoutJsonValue,
)
from projectkoios.ingestion.json.value import JsonValue
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorRawOutput(AbstractImmutableDataObject):
    """Bind canonical provider output to exact invocation inputs."""

    CONTRACT_VERSION: ClassVar[str] = "1.0"

    render_id: str
    resource_id: str
    preprocessing_id: str
    observations: CocoLayoutDetectorObservationInventory
    output_id: str = field(init=False)

    def __post_init__(self) -> None:
        render_id = LayoutValueValidation.require_text(
            "render_id", self.render_id
        )
        resource_id = LayoutValueValidation.require_text(
            "resource_id", self.resource_id
        )
        preprocessing_id = LayoutValueValidation.require_text(
            "preprocessing_id", self.preprocessing_id
        )
        if (
            type(self.observations)
            is not CocoLayoutDetectorObservationInventory
        ):
            raise TypeError(
                "observations must be CocoLayoutDetectorObservationInventory"
            )
        if any(
            observation.render_id != render_id
            for observation in self.observations
        ):
            raise ValueError("raw observations target another render")
        object.__setattr__(
            self,
            "output_id",
            stable_id(
                "coco-layout-detector-raw-output",
                self.CONTRACT_VERSION,
                render_id,
                resource_id,
                preprocessing_id,
                self.observations.inventory_id,
            ),
        )


class CocoLayoutDetectorRawOutputJsonContract(
    CocoLayoutJsonContract[CocoLayoutDetectorRawOutput]
):
    """Strictly parse and canonically replay exact detector output."""

    __slots__ = ()

    ROOT_FIELDS = frozenset(
        {
            "observations",
            "output_id",
            "preprocessing_id",
            "render_id",
            "resource_id",
            "schema_version",
        }
    )
    OBSERVATION_FIELDS = frozenset(
        {
            "bounding_box_xyxy_pixels",
            "confidence",
            "model_label_id",
            "observation_id",
            "producer_order",
        }
    )

    def to_json_value(self, value: CocoLayoutDetectorRawOutput) -> JsonValue:
        if type(value) is not CocoLayoutDetectorRawOutput:
            raise TypeError("value must be CocoLayoutDetectorRawOutput")
        return {
            "schema_version": value.CONTRACT_VERSION,
            "output_id": value.output_id,
            "render_id": value.render_id,
            "resource_id": value.resource_id,
            "preprocessing_id": value.preprocessing_id,
            "observations": [
                {
                    "observation_id": observation.observation_id,
                    "producer_order": producer_order,
                    "model_label_id": observation.model_label_id,
                    "bounding_box_xyxy_pixels": list(
                        observation.bounding_box_xyxy_pixels
                    ),
                    "confidence": observation.confidence,
                }
                for producer_order, observation in enumerate(value.observations)
            ],
        }

    def from_json_value(self, value: JsonValue) -> CocoLayoutDetectorRawOutput:
        root = CocoLayoutJsonValue.require_object(
            value,
            field="detector raw output",
            expected_fields=self.ROOT_FIELDS,
        )
        version = CocoLayoutJsonValue.require_string(
            root["schema_version"], field="schema_version"
        )
        if version != CocoLayoutDetectorRawOutput.CONTRACT_VERSION:
            raise ValueError("unsupported detector raw output version")
        render_id = CocoLayoutJsonValue.require_string(
            root["render_id"], field="render_id"
        )
        observations = CocoLayoutDetectorObservationInventory(
            *(
                self.observation_from_json_value(
                    item,
                    render_id=render_id,
                    expected_producer_order=producer_order,
                )
                for producer_order, item in enumerate(
                    CocoLayoutJsonValue.require_array(
                        root["observations"], field="observations"
                    )
                )
            )
        )
        output = CocoLayoutDetectorRawOutput(
            render_id=render_id,
            resource_id=CocoLayoutJsonValue.require_string(
                root["resource_id"], field="resource_id"
            ),
            preprocessing_id=CocoLayoutJsonValue.require_string(
                root["preprocessing_id"], field="preprocessing_id"
            ),
            observations=observations,
        )
        if (
            CocoLayoutJsonValue.require_string(
                root["output_id"], field="output_id"
            )
            != output.output_id
        ):
            raise ValueError("detector raw output identity is inconsistent")
        return output

    def observation_from_json_value(
        self,
        value: JsonValue,
        *,
        render_id: str,
        expected_producer_order: int,
    ) -> CocoLayoutDetectorObservation:
        """Reconstruct one exact frozen detector observation."""
        item = CocoLayoutJsonValue.require_object(
            value,
            field="observation",
            expected_fields=self.OBSERVATION_FIELDS,
        )
        box = tuple(
            CocoLayoutJsonValue.require_number(
                component, field="bounding_box_xyxy_pixels"
            )
            for component in CocoLayoutJsonValue.require_array(
                item["bounding_box_xyxy_pixels"],
                field="bounding_box_xyxy_pixels",
            )
        )
        if len(box) != 4:
            raise ValueError("detector observation box must have four values")
        producer_order = CocoLayoutJsonValue.require_integer(
            item["producer_order"], field="producer_order"
        )
        if producer_order != expected_producer_order:
            raise ValueError("detector producer order must be contiguous")
        observation = CocoLayoutDetectorObservation(
            render_id=render_id,
            model_label_id=CocoLayoutJsonValue.require_integer(
                item["model_label_id"], field="model_label_id"
            ),
            bounding_box_xyxy_pixels=(box[0], box[1], box[2], box[3]),
            confidence=CocoLayoutJsonValue.require_number(
                item["confidence"], field="confidence"
            ),
        )
        if (
            CocoLayoutJsonValue.require_string(
                item["observation_id"], field="observation_id"
            )
            != observation.observation_id
        ):
            raise ValueError("detector observation identity is inconsistent")
        return observation
