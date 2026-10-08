"""Closed visual-to-text reading association roles."""

from enum import StrEnum


class ReadingAssociationRole(StrEnum):
    """Mechanical source association role without acceptance semantics."""

    CAPTION = "caption"
    LEGEND = "legend"
    NOTE = "note"
    SUBFIGURE_LABEL = "subfigure_label"
    TITLE = "title"
