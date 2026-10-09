"""Typed resource-limit failure for page projection."""

from projectkoios.ingestion.page.projection.error import PageProjectionError


class PageProjectionLimitError(PageProjectionError):
    """Report a page-projection resource ceiling violation."""
