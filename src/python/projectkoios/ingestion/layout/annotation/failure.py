"""Labels for specific layout-analysis failure modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.kind import LayoutFailureKind
from projectkoios.ingestion.layout.annotation.limits.definition import (
    MAX_LAYOUT_REFERENCES_PER_ANNOTATION,
)
from projectkoios.ingestion.layout.annotation.limits.error import (
    LayoutAnnotationLimitError,
)
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutFailureAnnotation(AbstractImmutableDataObject):
    """Label one observed failure against explicit affected identities."""

    CONTRACT_NAME: ClassVar[str] = "layout-failure-annotation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    failure_annotation_id: str
    case_id: str
    kind: LayoutFailureKind
    block_ids: tuple[str, ...]
    proposal_ids: tuple[str, ...]
    region_annotation_ids: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        kind: LayoutFailureKind,
        block_ids: tuple[str, ...] = (),
        proposal_ids: tuple[str, ...] = (),
        region_annotation_ids: tuple[str, ...] = (),
    ) -> LayoutFailureAnnotation:
        """Create one stable failure label over exact affected identities."""
        case = LayoutValueValidation.require_text("case_id", case_id)
        if not isinstance(kind, LayoutFailureKind):
            raise TypeError("kind must be LayoutFailureKind")
        cls.validate_references(
            block_ids=block_ids,
            proposal_ids=proposal_ids,
            region_annotation_ids=region_annotation_ids,
        )
        annotation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            case,
            kind,
            block_ids,
            proposal_ids,
            region_annotation_ids,
        )
        return cls(
            failure_annotation_id=annotation_id,
            case_id=case,
            kind=kind,
            block_ids=block_ids,
            proposal_ids=proposal_ids,
            region_annotation_ids=region_annotation_ids,
        )

    @staticmethod
    def validate_references(
        *,
        block_ids: tuple[str, ...],
        proposal_ids: tuple[str, ...],
        region_annotation_ids: tuple[str, ...],
    ) -> None:
        """Require one or more unique, bounded affected identities."""
        if (
            len(block_ids) + len(proposal_ids) + len(region_annotation_ids)
            > MAX_LAYOUT_REFERENCES_PER_ANNOTATION
        ):
            raise LayoutAnnotationLimitError(
                "failure references exceed implementation maximum"
            )
        for name, values in (
            ("block_ids", block_ids),
            ("proposal_ids", proposal_ids),
            ("region_annotation_ids", region_annotation_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{name} must contain non-empty IDs")
            bounded_values = tuple(
                LayoutValueValidation.require_text(name, value)
                for value in values
            )
            if len(set(bounded_values)) != len(bounded_values):
                raise ValueError(f"{name} must contain unique IDs")
        if not (block_ids or proposal_ids or region_annotation_ids):
            raise ValueError(
                "failure annotation must identify affected evidence"
            )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout failure annotation contract")
        LayoutValueValidation.require_text("case_id", self.case_id)
        if not isinstance(self.kind, LayoutFailureKind):
            raise TypeError("kind must be LayoutFailureKind")
        self.validate_references(
            block_ids=self.block_ids,
            proposal_ids=self.proposal_ids,
            region_annotation_ids=self.region_annotation_ids,
        )
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.case_id,
            self.kind,
            self.block_ids,
            self.proposal_ids,
            self.region_annotation_ids,
        )
        if self.failure_annotation_id != expected:
            raise ValueError("layout failure annotation ID is inconsistent")
