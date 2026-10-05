from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.transcription.derivation.raw_block import (
    RawBlockTranscriptionDerivation,
)


def test__rawblocktranscriptionderivation__has_nominal_domain_role() -> None:
    assert issubclass(RawBlockTranscriptionDerivation, AbstractDerivation)
