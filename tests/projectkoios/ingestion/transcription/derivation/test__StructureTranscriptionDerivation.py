from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.structure import (
    StructureTranscriptionDerivation,
)


def test__structuretranscriptionderivation__has_nominal_domain_role() -> None:
    assert issubclass(StructureTranscriptionDerivation, AbstractDerivation)
