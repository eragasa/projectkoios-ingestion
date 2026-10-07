"""Human-authored reading-order annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation
from projectkoios.ingestion.models import Metadata


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderAnnotation(AbstractImmutableDataObject):
    """Require one native block to precede another in corrected order."""

    CONTRACT_NAME: ClassVar[str] = "layout-reading-order-annotation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    order_annotation_id: str
    case_id: str
    before_block_id: str
    after_block_id: str
    evidence: Metadata
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        before_block_id: str,
        after_block_id: str,
        evidence: Metadata = (),
    ) -> LayoutReadingOrderAnnotation:
        """Create one stable directed reading-order edge."""
        normalized_evidence = LayoutValueValidation.normalize_metadata(evidence)
        annotation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            case_id,
            before_block_id,
            after_block_id,
            normalized_evidence,
        )
        return cls(
            order_annotation_id=annotation_id,
            case_id=case_id,
            before_block_id=before_block_id,
            after_block_id=after_block_id,
            evidence=normalized_evidence,
        )

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported layout reading-order annotation contract"
            )
        LayoutValueValidation.require_text("case_id", self.case_id)
        LayoutValueValidation.require_text(
            "before_block_id", self.before_block_id
        )
        LayoutValueValidation.require_text(
            "after_block_id", self.after_block_id
        )
        if self.before_block_id == self.after_block_id:
            raise ValueError(
                "reading-order edge cannot reference one block twice"
            )
        evidence = LayoutValueValidation.normalize_metadata(self.evidence)
        object.__setattr__(self, "evidence", evidence)
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.case_id,
            self.before_block_id,
            self.after_block_id,
            evidence,
        )
        if self.order_annotation_id != expected:
            raise ValueError(
                "layout reading-order annotation ID is inconsistent"
            )
