from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.warning import (
    TranscriptionWarningDerivation,
)


def test__transcriptionwarningderivation__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionWarningDerivation, AbstractDerivation)
