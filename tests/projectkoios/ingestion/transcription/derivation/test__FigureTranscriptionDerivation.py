from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.figure import (
    FigureTranscriptionDerivation,
)


def test__figuretranscriptionderivation__has_nominal_domain_role() -> None:
    assert issubclass(FigureTranscriptionDerivation, AbstractDerivation)
