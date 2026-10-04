from projectkoios.ingestion.base import AbstractValidation
from projectkoios.ingestion.transcription.omission.validation.coverage import (
    TranscriptionOmissionCoverageValidation,
)


def test__omission_coverage_validation__has_nominal_domain_role() -> None:
    assert issubclass(
        TranscriptionOmissionCoverageValidation, AbstractValidation
    )
