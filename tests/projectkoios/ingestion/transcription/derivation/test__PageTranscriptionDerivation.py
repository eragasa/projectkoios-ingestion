from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.page import (
    PageTranscriptionDerivation,
)


def test__pagetranscriptionderivation__has_nominal_domain_role() -> None:
    assert issubclass(PageTranscriptionDerivation, AbstractDerivation)
