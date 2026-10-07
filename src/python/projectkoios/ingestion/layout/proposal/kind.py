"""Backend-neutral semantic layout-region kinds."""

from enum import StrEnum


class LayoutRegionKind(StrEnum):
    """Semantic region proposed or annotated on a rendered page."""

    TEXT = "text"
    TITLE = "title"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    EQUATION = "equation"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    SIDEBAR = "sidebar"
    OTHER = "other"
