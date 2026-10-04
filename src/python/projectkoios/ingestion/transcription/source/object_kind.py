from __future__ import annotations

from enum import StrEnum


class TranscriptionSourceObjectKind(StrEnum):
    PAGE = "page"
    RAW_BLOCK = "raw_block"
    STRUCTURE_NODE = "structure_node"
    EQUATION_CANDIDATE = "equation_candidate"
    TABLE_STRUCTURE = "table_structure"
    FIGURE_CANDIDATE = "figure_candidate"
