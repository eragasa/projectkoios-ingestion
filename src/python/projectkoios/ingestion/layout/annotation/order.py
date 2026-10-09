"""Reading-order annotations and graph validation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import ClassVar

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.validation.value import LayoutValueValidation


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderAnnotation(AbstractImmutableDataObject):
    """Require one native block to precede another in corrected order."""

    CONTRACT_NAME: ClassVar[str] = "layout-reading-order-annotation"
    CONTRACT_VERSION: ClassVar[str] = "1.0"

    order_annotation_id: str
    case_id: str
    before_block_id: str
    after_block_id: str
    contract_version: str = CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        before_block_id: str,
        after_block_id: str,
    ) -> LayoutReadingOrderAnnotation:
        """Create one stable directed reading-order edge."""
        case = LayoutValueValidation.require_text("case_id", case_id)
        before = LayoutValueValidation.require_text(
            "before_block_id", before_block_id
        )
        after = LayoutValueValidation.require_text(
            "after_block_id", after_block_id
        )
        if before == after:
            raise ValueError(
                "reading-order edge cannot reference one block twice"
            )
        annotation_id = stable_id(
            cls.CONTRACT_NAME,
            cls.CONTRACT_VERSION,
            case,
            before,
            after,
        )
        return cls(
            order_annotation_id=annotation_id,
            case_id=case,
            before_block_id=before,
            after_block_id=after,
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
        expected = stable_id(
            self.CONTRACT_NAME,
            self.CONTRACT_VERSION,
            self.case_id,
            self.before_block_id,
            self.after_block_id,
        )
        if self.order_annotation_id != expected:
            raise ValueError(
                "layout reading-order annotation ID is inconsistent"
            )


class LayoutReadingOrderValidation:
    """Own bounded validation of reading-order graph evidence."""

    __slots__ = ()

    @staticmethod
    def validate(
        *,
        valid_block_ids: set[str],
        edges: tuple[LayoutReadingOrderAnnotation, ...],
    ) -> None:
        """Reject unknown, duplicate, self-referential, and cyclic edges."""
        endpoint_pairs: set[tuple[str, str]] = set()
        outgoing: dict[str, set[str]] = {
            block_id: set() for block_id in valid_block_ids
        }
        incoming = {block_id: 0 for block_id in valid_block_ids}
        for edge in edges:
            endpoints = (edge.before_block_id, edge.after_block_id)
            if set(endpoints) - valid_block_ids:
                raise ValueError(
                    "order edge references an unknown native block"
                )
            if endpoints in endpoint_pairs:
                raise ValueError("reading-order endpoint pairs must be unique")
            endpoint_pairs.add(endpoints)
            outgoing[edge.before_block_id].add(edge.after_block_id)
            incoming[edge.after_block_id] += 1

        ready = deque(
            block_id for block_id, count in incoming.items() if count == 0
        )
        visited = 0
        while ready:
            block_id = ready.popleft()
            visited += 1
            for successor in outgoing[block_id]:
                incoming[successor] -= 1
                if incoming[successor] == 0:
                    ready.append(successor)
        if visited != len(valid_block_ids):
            raise ValueError("reading-order annotations contain a cycle")
