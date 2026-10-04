from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.item.projection_validation import (
    TranscriptionItemProjectionValidation,
)


def test__transcriptionitemprojectionvalidation__has_nominal_domain_role() -> (
    None
):
    assert issubclass(TranscriptionItemProjectionValidation, AbstractValidation)
