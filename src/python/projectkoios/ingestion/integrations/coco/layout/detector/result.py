"""Deterministic results from frozen local detector observations."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.base.actionizer.result import (
    AbstractDataObjectActionResult,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.integrations.coco.layout.detection import (
    CocoLayoutDetection,
    CocoLayoutDetectionInventory,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation

from .adaptation import (
    CocoLayoutDetectorAdaptation,
    CocoLayoutDetectorAdaptationInventory,
)
from .label import (
    CocoLayoutDetectorLabelDisposition,
    CocoLayoutDetectorLabelMapping,
)
from .limitation import (
    CocoLayoutDetectorLimitation,
    CocoLayoutDetectorLimitationCode,
    CocoLayoutDetectorLimitationInventory,
)
from .observation import CocoLayoutDetectorObservation
from .request import CocoLayoutDetectorRequest


@dataclass(frozen=True, slots=True)
class CocoLayoutDetectorResult(AbstractDataObjectActionResult):
    """Expose canonical accepted detections and explicit exclusions."""

    request: CocoLayoutDetectorRequest
    adaptations: CocoLayoutDetectorAdaptationInventory
    limitations: CocoLayoutDetectorLimitationInventory
    actionizer_name: str
    actionizer_version: str
    result_id: str = field(init=False)

    @classmethod
    def create(
        cls,
        *,
        request: CocoLayoutDetectorRequest,
        actionizer_name: str,
        actionizer_version: str,
    ) -> CocoLayoutDetectorResult:
        """Derive canonical IDs and exclusions from one complete request."""
        if type(request) is not CocoLayoutDetectorRequest:
            raise TypeError("request must be CocoLayoutDetectorRequest")
        adaptations, limitations = cls.derive(request)
        return cls(
            request=request,
            adaptations=adaptations,
            limitations=limitations,
            actionizer_name=actionizer_name,
            actionizer_version=actionizer_version,
        )

    @staticmethod
    def derive(
        request: CocoLayoutDetectorRequest,
    ) -> tuple[
        CocoLayoutDetectorAdaptationInventory,
        CocoLayoutDetectorLimitationInventory,
    ]:
        """Classify observations and assign canonical COCO annotation IDs."""
        if type(request) is not CocoLayoutDetectorRequest:
            raise TypeError("request must be CocoLayoutDetectorRequest")
        configuration = request.configuration
        accepted: list[
            tuple[
                CocoLayoutDetectorObservation,
                CocoLayoutDetectorLabelMapping,
                tuple[float, float, float, float],
            ]
        ] = []
        limitations: list[CocoLayoutDetectorLimitation] = []
        for observation in request.observations:
            mapping = configuration.label_mappings.require(
                observation.model_label_id
            )
            # Unsupported labels take precedence over score filtering so an
            # extension label never disappears as a generic low-score record.
            if (
                mapping.disposition
                is CocoLayoutDetectorLabelDisposition.UNSUPPORTED
            ):
                limitations.append(
                    CocoLayoutDetectorLimitation(
                        observation=observation,
                        code=CocoLayoutDetectorLimitationCode.UNSUPPORTED_LABEL,
                    )
                )
                continue
            if observation.confidence < configuration.minimum_confidence:
                limitations.append(
                    CocoLayoutDetectorLimitation(
                        observation=observation,
                        code=(
                            CocoLayoutDetectorLimitationCode.BELOW_CONFIDENCE_THRESHOLD
                        ),
                    )
                )
                continue
            x1, y1, x2, y2 = observation.bounding_box_xyxy_pixels
            # COCO stores XYWH, but exact XYXY reconstruction is required so
            # interchange cannot silently perturb render-space coordinates.
            xywh = (x1, y1, x2 - x1, y2 - y1)
            if (x1 + xywh[2], y1 + xywh[3]) != (x2, y2):
                raise ValueError(
                    "detector coordinates are not exactly COCO round-trippable"
                )
            accepted.append((observation, mapping, xywh))
        # Producer order remains in the request; annotation IDs instead follow
        # the profile's canonical semantic order for deterministic interchange.
        accepted.sort(
            key=lambda item: (
                item[1].category_id,
                item[2],
                item[0].confidence,
                item[0].observation_id,
            )
        )
        adaptations: list[CocoLayoutDetectorAdaptation] = []
        for annotation_id, (observation, mapping, xywh) in enumerate(
            accepted, start=1
        ):
            if mapping.category_id is None:
                raise ValueError("accepted detector label has no category")
            adaptations.append(
                CocoLayoutDetectorAdaptation(
                    observation=observation,
                    mapping=mapping,
                    detection=CocoLayoutDetection(
                        annotation_id=annotation_id,
                        image_id=request.image.image_id,
                        category_id=mapping.category_id,
                        bbox_xywh_pixels=xywh,
                        confidence=observation.confidence,
                    ),
                )
            )
        return (
            CocoLayoutDetectorAdaptationInventory(*adaptations),
            CocoLayoutDetectorLimitationInventory(*limitations),
        )

    def __post_init__(self) -> None:
        if type(self.request) is not CocoLayoutDetectorRequest:
            raise TypeError("request must be CocoLayoutDetectorRequest")
        if type(self.adaptations) is not CocoLayoutDetectorAdaptationInventory:
            raise TypeError(
                "adaptations must be CocoLayoutDetectorAdaptationInventory"
            )
        if type(self.limitations) is not CocoLayoutDetectorLimitationInventory:
            raise TypeError(
                "limitations must be CocoLayoutDetectorLimitationInventory"
            )
        actionizer_name = LayoutValueValidation.require_text(
            "actionizer_name", self.actionizer_name
        )
        actionizer_version = LayoutValueValidation.require_text(
            "actionizer_version", self.actionizer_version
        )
        expected_adaptations, expected_limitations = self.derive(self.request)
        if (
            self.adaptations != expected_adaptations
            or self.limitations != expected_limitations
        ):
            raise ValueError(
                "detector result differs from deterministic request derivation"
            )
        accepted_ids = {
            adaptation.observation.observation_id
            for adaptation in self.adaptations
        }
        limited_ids = {
            limitation.observation.observation_id
            for limitation in self.limitations
        }
        if accepted_ids & limited_ids or len(accepted_ids | limited_ids) != len(
            self.request.observations
        ):
            raise ValueError(
                "detector result does not partition all observations"
            )
        object.__setattr__(self, "actionizer_name", actionizer_name)
        object.__setattr__(self, "actionizer_version", actionizer_version)
        object.__setattr__(
            self,
            "result_id",
            stable_id(
                "coco-layout-detector-result",
                self.request.request_id,
                self.adaptations.inventory_id,
                self.limitations.inventory_id,
                actionizer_name,
                actionizer_version,
            ),
        )

    @property
    def detections(self) -> CocoLayoutDetectionInventory:
        """Return canonical accepted COCO detections."""
        return CocoLayoutDetectionInventory(
            *(adaptation.detection for adaptation in self.adaptations)
        )
