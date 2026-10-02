from __future__ import annotations

from collections.abc import Iterable
from typing import BinaryIO, Protocol

from projectkoios.ingestion.models import SourceDocument
from projectkoios.ingestion.pdf.models import (
    PageRegionSelection,
    RegionRenderConfiguration,
    RenderedRegion,
)


class PdfRegionRenderLimitError(ValueError):
    """Raised before raster allocation when a configured limit is exceeded."""


class PdfRegionRenderer(Protocol):
    """Backend-neutral contract for bounded PDF region renderers."""

    name: str
    version: str
    configuration: RegionRenderConfiguration

    @property
    def configuration_digest(self) -> str: ...

    def render(
        self,
        source: SourceDocument,
        content: BinaryIO,
        selections: Iterable[PageRegionSelection],
    ) -> tuple[RenderedRegion, ...]: ...
