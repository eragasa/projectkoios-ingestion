"""Human-authored layout failure annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.annotation.kind import LayoutFailureKind
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.models import Metadata


@dataclass(frozen=True, slots=True)
class LayoutFailureAnnotation(AbstractImmutableDataObject):
    """Classify one observed layout failure without accepting a correction."""

    CONTRACT_NAME: ClassVar[str] = "layout-failure-annotation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    failure_annotation_id: str
    case_id: str
    kind: LayoutFailureKind
    block_ids: tuple[str, ...]
    proposal_ids: tuple[str, ...]
    region_annotation_ids: tuple[str, ...]
    evidence: Metadata
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
        evidence: Metadata = (),
    ) -> LayoutFailureAnnotation:
        """Create one stable failure label over exact affected identities."""
        normalized_evidence = LayoutValueValidation.normalize_metadata(evidence)
        annotation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            case_id,
            kind,
            block_ids,
            proposal_ids,
            region_annotation_ids,
            normalized_evidence,
        )
        return cls(
            failure_annotation_id=annotation_id,
            case_id=case_id,
            kind=kind,
            block_ids=block_ids,
            proposal_ids=proposal_ids,
            region_annotation_ids=region_annotation_ids,
            evidence=normalized_evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError("unsupported layout failure annotation contract")
        LayoutValueValidation.require_text("case_id", self.case_id)
        if not isinstance(self.kind, LayoutFailureKind):
            raise TypeError("kind must be LayoutFailureKind")
        for name, values in (
            ("block_ids", self.block_ids),
            ("proposal_ids", self.proposal_ids),
            ("region_annotation_ids", self.region_annotation_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(set(values)) != len(values) or any(
                not value for value in values
            ):
                raise ValueError(f"{name} must contain unique non-empty IDs")
        if not (
            self.block_ids
            or self.proposal_ids
            or self.region_annotation_ids
            or self.evidence
        ):
            raise ValueError("failure annotation must identify evidence")
        evidence = LayoutValueValidation.normalize_metadata(self.evidence)
        object.__setattr__(self, "evidence", evidence)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.case_id,
            self.kind,
            self.block_ids,
            self.proposal_ids,
            self.region_annotation_ids,
            evidence,
        )
        if self.failure_annotation_id != expected:
            raise ValueError("layout failure annotation ID is inconsistent")
