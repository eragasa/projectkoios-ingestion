from dataclasses import fields

from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.request.validation import (
    TranscriptionRequestValidation,
)


def test__transcription_request_validation__retains_validated_subjects() -> (
    None
):
    assert issubclass(TranscriptionRequestValidation, AbstractValidation)
    assert {field.name for field in fields(TranscriptionRequestValidation)} >= {
        "document",
        "structure_analysis",
        "equation_detection_result",
        "table_structure_result",
        "figure_detection_result",
        "configuration",
        "artifact_inventory",
    }
