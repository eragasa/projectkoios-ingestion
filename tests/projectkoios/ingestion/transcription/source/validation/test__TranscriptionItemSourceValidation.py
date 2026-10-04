from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.source.validation.item import (
    TranscriptionItemSourceValidation,
)


def test__transcriptionitemsourcevalidation__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionItemSourceValidation, AbstractValidation)
