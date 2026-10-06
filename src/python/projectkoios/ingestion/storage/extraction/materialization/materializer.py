"""Nominal materializer port for extraction read models."""

from __future__ import annotations

from abc import ABC

from projectkoios.ingestion.base.materializer.actionizer import Materializer
from projectkoios.ingestion.storage.extraction.materialization.configuration import (  # noqa: E501
    ExtractionProjectionMaterializationConfiguration,
)
from projectkoios.ingestion.storage.extraction.materialization.evidence.model import (  # noqa: E501
    ExtractionProjectionMaterializationEvidence,
)
from projectkoios.ingestion.storage.extraction.materialization.target import (
    ExtractionProjectionTargetIdentity,
)
from projectkoios.ingestion.storage.extraction.projection.read.model import (
    ExtractionReadModel,
)


class AbstractExtractionProjectionMaterializer(
    Materializer[
        ExtractionReadModel,
        ExtractionProjectionTargetIdentity,
        ExtractionProjectionMaterializationConfiguration,
        ExtractionProjectionMaterializationEvidence,
    ],
    ABC,
):
    """Define the exact effectful port consumed by the extraction pipeline."""

    __slots__ = ()

    authority_requirement = "extraction_projection_write"
    projection_type = ExtractionReadModel
    target_type = ExtractionProjectionTargetIdentity
    configuration_type = ExtractionProjectionMaterializationConfiguration
    evidence_type = ExtractionProjectionMaterializationEvidence
