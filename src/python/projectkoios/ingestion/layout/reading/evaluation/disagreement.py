"""Exact pairwise replica disagreement evidence."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.identity import stable_id

from .identity import LayoutReadingOrderReplicaEvidenceIdentityInventory


@dataclass(frozen=True, slots=True)
class LayoutReadingOrderReplicaDisagreementPair(AbstractImmutableDataObject):
    """Bind opposite claimed precedence for one candidate-oriented pair."""

    candidate_first_element_id: str
    candidate_second_element_id: str
    forward_evidence_ids: LayoutReadingOrderReplicaEvidenceIdentityInventory
    reverse_evidence_ids: LayoutReadingOrderReplicaEvidenceIdentityInventory
    disagreement_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.candidate_first_element_id, str
        ) or not isinstance(self.candidate_second_element_id, str):
            raise TypeError("disagreement element IDs must be strings")
        if (
            not self.candidate_first_element_id
            or not self.candidate_second_element_id
            or self.candidate_first_element_id
            == self.candidate_second_element_id
        ):
            raise ValueError("disagreement requires two distinct element IDs")
        if (
            type(self.forward_evidence_ids)
            is not LayoutReadingOrderReplicaEvidenceIdentityInventory
        ):
            raise TypeError(
                "forward_evidence_ids must be an identity inventory"
            )
        if (
            type(self.reverse_evidence_ids)
            is not LayoutReadingOrderReplicaEvidenceIdentityInventory
        ):
            raise TypeError(
                "reverse_evidence_ids must be an identity inventory"
            )
        if (
            len(self.forward_evidence_ids) == 0
            or len(self.reverse_evidence_ids) == 0
        ):
            raise ValueError(
                "disagreement requires evidence for both directions"
            )
        if set(self.forward_evidence_ids) & set(self.reverse_evidence_ids):
            raise ValueError("one replica cannot support both pair directions")
        object.__setattr__(
            self,
            "disagreement_id",
            stable_id(
                "layout-reading-order-replica-disagreement-pair",
                self.candidate_first_element_id,
                self.candidate_second_element_id,
                self.forward_evidence_ids.inventory_id,
                self.reverse_evidence_ids.inventory_id,
            ),
        )


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderReplicaDisagreementPairInventory:
    """Own disagreements in deterministic candidate-pair order."""

    _pairs: tuple[LayoutReadingOrderReplicaDisagreementPair, ...] = field(
        repr=True
    )
    inventory_id: str = field(init=False)

    def __init__(
        self, *pairs: LayoutReadingOrderReplicaDisagreementPair
    ) -> None:
        values = tuple(pairs)
        if any(
            type(item) is not LayoutReadingOrderReplicaDisagreementPair
            for item in values
        ):
            raise TypeError("pairs must be replica disagreement values")
        keys = tuple(
            (item.candidate_first_element_id, item.candidate_second_element_id)
            for item in values
        )
        if len(keys) != len(set(keys)):
            raise ValueError("replica disagreement pairs must be unique")
        object.__setattr__(self, "_pairs", values)
        object.__setattr__(
            self,
            "inventory_id",
            stable_id(
                "layout-reading-order-replica-disagreement-pair-inventory",
                tuple(item.disagreement_id for item in values),
            ),
        )

    def __iter__(self) -> Iterator[LayoutReadingOrderReplicaDisagreementPair]:
        return iter(self._pairs)

    def __len__(self) -> int:
        return len(self._pairs)
