from __future__ import annotations

from enum import StrEnum


class TranscriptionOrderStatus(StrEnum):
    PAGE_ANCHOR = "page_anchor"
    PROPOSED_GEOMETRIC = "proposed_geometric"
    PROPOSED_STRUCTURE = "proposed_structure"
    UNCERTAIN_SOURCE_ORDER = "uncertain_source_order"
