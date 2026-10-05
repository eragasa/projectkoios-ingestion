from projectkoios.ingestion.base.immutable import AbstractImmutableDataObject
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)


def test__abstract_transcription_data_object__owns_contract_bounds() -> None:
    assert issubclass(
        AbstractTranscriptionDataObject,
        AbstractImmutableDataObject,
    )
    assert AbstractTranscriptionDataObject.CONTRACT_VERSION == "1.0"
    assert AbstractTranscriptionDataObject.COMPOSER_VERSION == "1"
    assert AbstractTranscriptionDataObject.MAX_INPUT_BLOCKS == 65_536
    assert AbstractTranscriptionDataObject.MAX_RESULT_BYTES == 128_000_000
