from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.equation import (
    EquationTranscriptionDerivation,
)


def test__equationtranscriptionderivation__has_nominal_domain_role() -> None:
    assert issubclass(EquationTranscriptionDerivation, AbstractDerivation)
