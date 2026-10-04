from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.structure_disposition import (  # noqa: E501
    TranscriptionStructureDisposition,
)


def test__transcriptionstructuredisposition__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionStructureDisposition, AbstractDerivation)
