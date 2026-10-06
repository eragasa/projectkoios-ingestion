from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.disposition.structure import (  # noqa: E501
    TranscriptionStructureDisposition,
)


def test__transcriptionstructuredisposition__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionStructureDisposition, AbstractDerivation)
