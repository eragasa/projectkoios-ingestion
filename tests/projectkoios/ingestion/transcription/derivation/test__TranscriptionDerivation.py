from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.model import (
    TranscriptionDerivation,
)


def test__transcription_derivation__has_nominal_derivation_role() -> None:
    assert issubclass(TranscriptionDerivation, AbstractDerivation)
