"""TableCellRole table-structure domain object."""

from __future__ import annotations

from enum import StrEnum


class TableCellRole(StrEnum):
    HEADER = "header"
    BODY = "body"
    UNKNOWN = "unknown"
