"""LayoutParser proposal-adaptation configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from projectkoios.ingestion.base.actionizer.configuration import (
    AbstractActionConfiguration,
)
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.proposal.kind import LayoutRegionKind
from projectkoios.ingestion.layout.proposal.limits.definition import (
    MAX_LAYOUT_REGION_PROPOSALS,
)
from projectkoios.ingestion.layout.proposal.limits.error import (
    LayoutProposalLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.sha256.hash import SHA256Hash

from .limits.definition import (
    MAX_LAYOUT_PARSER_LABEL_CHARACTERS,
    MAX_LAYOUT_PARSER_LABEL_MAPPING_CHARACTERS,
    MAX_LAYOUT_PARSER_LABEL_MAPPINGS,
)
from .limits.error import LayoutParserLimitError


@dataclass(frozen=True, slots=True)
class LayoutParserProposalConfiguration(AbstractActionConfiguration):
    """Bind one exact LayoutParser runtime, backend, model, and label map."""

    CONTRACT_NAME: ClassVar[str] = "layout-parser-proposal-configuration"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    package_version: str
    backend_name: str
    backend_version: str
    model_identity: str
    model_sha256: SHA256Hash
    label_mapping: tuple[tuple[str, LayoutRegionKind], ...]
    max_detections: int = MAX_LAYOUT_REGION_PROPOSALS
    configuration_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("package_version", self.package_version),
            ("backend_name", self.backend_name),
            ("backend_version", self.backend_version),
            ("model_identity", self.model_identity),
        ):
            LayoutValueValidation.require_text(name, value)
        digest = SHA256Hash(self.model_sha256)
        object.__setattr__(self, "model_sha256", digest)
        if not isinstance(self.label_mapping, tuple) or not self.label_mapping:
            raise ValueError("label_mapping must be a non-empty tuple")
        if len(self.label_mapping) > MAX_LAYOUT_PARSER_LABEL_MAPPINGS:
            raise LayoutParserLimitError(
                "label_mapping exceeds implementation maximum"
            )
        labels: set[str] = set()
        label_characters = 0
        for item in self.label_mapping:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("label_mapping items must be two-value tuples")
            label = LayoutValueValidation.require_text("model label", item[0])
            if len(label) > MAX_LAYOUT_PARSER_LABEL_CHARACTERS:
                raise LayoutParserLimitError(
                    "model label exceeds implementation character limit"
                )
            if label in labels:
                raise ValueError("model labels must be unique")
            labels.add(label)
            label_characters += len(label)
            if label_characters > MAX_LAYOUT_PARSER_LABEL_MAPPING_CHARACTERS:
                raise LayoutParserLimitError(
                    "label_mapping exceeds aggregate character limit"
                )
            if not isinstance(item[1], LayoutRegionKind):
                raise TypeError("model labels must map to LayoutRegionKind")
        if tuple(sorted(self.label_mapping, key=lambda item: item[0])) != (
            self.label_mapping
        ):
            raise ValueError("label_mapping must be sorted by model label")
        maximum = LayoutValueValidation.require_positive_integer(
            "max_detections", self.max_detections
        )
        if maximum > MAX_LAYOUT_REGION_PROPOSALS:
            raise LayoutProposalLimitError(
                "max_detections exceeds implementation maximum"
            )
        object.__setattr__(self, "configuration_id", self.configuration_digest)

    @property
    def configuration_digest(self) -> str:
        """Return stable identity over every adapter choice and resource."""
        return stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.package_version,
            self.backend_name,
            self.backend_version,
            self.model_identity,
            self.model_sha256,
            self.label_mapping,
            self.max_detections,
        )
