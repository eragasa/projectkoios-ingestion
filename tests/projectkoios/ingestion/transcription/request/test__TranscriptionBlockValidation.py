from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.request.block_validation import (
    TranscriptionBlockValidation,
)


def test__transcriptionblockvalidation__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionBlockValidation, AbstractValidation)
