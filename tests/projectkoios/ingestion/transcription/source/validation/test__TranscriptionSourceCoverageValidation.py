from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.source.validation.coverage import (
    TranscriptionSourceCoverageValidation,
)


def test__transcriptionsourcecoveragevalidation__has_nominal_domain_role() -> (
    None
):
    assert issubclass(TranscriptionSourceCoverageValidation, AbstractValidation)
