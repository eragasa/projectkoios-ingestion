from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.transcription.evidence.warning_derivation import (
    TranscriptionWarningDerivation,
)


def test__transcriptionwarningderivation__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionWarningDerivation, AbstractDerivation)
