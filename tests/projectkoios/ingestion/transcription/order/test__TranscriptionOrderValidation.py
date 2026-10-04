from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.order.validation import (
    TranscriptionOrderValidation,
)


def test__transcriptionordervalidation__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionOrderValidation, AbstractValidation)
