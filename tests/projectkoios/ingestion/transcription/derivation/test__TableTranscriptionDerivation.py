from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.table import (
    TableTranscriptionDerivation,
)


def test__tabletranscriptionderivation__has_nominal_domain_role() -> None:
    assert issubclass(TableTranscriptionDerivation, AbstractDerivation)
