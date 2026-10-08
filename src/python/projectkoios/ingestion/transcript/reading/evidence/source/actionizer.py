"""Backend-neutral canonical reading-evidence source action boundary."""

from __future__ import annotations

from abc import ABC

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.transcript.reading.evidence.source.request import (
    ReadingEvidenceSourceRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.source.result import (
    ReadingEvidenceSourceResult,
)


class ReadingEvidenceSourceActionizer(
    DataObjectActionizer[
        ReadingEvidenceSourceRequest,
        ReadingEvidenceSourceResult,
    ],
    ABC,
):
    """Require providers to return only verified canonical source values."""

    __slots__ = ()
