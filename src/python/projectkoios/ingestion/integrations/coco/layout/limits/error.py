"""COCO layout-adaptation limit failures."""


class CocoLayoutLimitError(ValueError):
    """Signal that COCO layout evidence exceeds a hard bound."""
