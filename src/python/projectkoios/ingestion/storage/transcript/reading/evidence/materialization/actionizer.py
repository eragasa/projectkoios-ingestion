"""Nominal materializer port for canonical reading-evidence read models."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.materializer.actionizer import Materializer
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.configuration import (  # noqa: E501
    ReadingEvidenceMaterializationConfiguration,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.evidence import (  # noqa: E501
    ReadingEvidenceMaterializationEvidence,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.materialization.target import (  # noqa: E501
    ReadingEvidenceMaterializationTarget,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.read.model import (  # noqa: E501
    ReadingEvidenceReadModel,
)


class ReadingEvidenceMaterializer(
    Materializer[
        ReadingEvidenceReadModel,
        ReadingEvidenceMaterializationTarget,
        ReadingEvidenceMaterializationConfiguration,
        ReadingEvidenceMaterializationEvidence,
    ],
    ABC,
):
    """Define the exact effectful port implemented by storage adapters."""

    __slots__ = ()

    authority_requirement = "reading_evidence_projection_write"
    projection_type = ReadingEvidenceReadModel
    target_type = ReadingEvidenceMaterializationTarget
    configuration_type = ReadingEvidenceMaterializationConfiguration
    evidence_type = ReadingEvidenceMaterializationEvidence
