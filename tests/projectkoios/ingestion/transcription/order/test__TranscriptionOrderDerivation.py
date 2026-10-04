from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.transcription.order.derivation import (
    TranscriptionOrderDerivation,
)


def test__transcriptionorderderivation__has_nominal_domain_role() -> None:
    assert issubclass(TranscriptionOrderDerivation, AbstractDerivation)
