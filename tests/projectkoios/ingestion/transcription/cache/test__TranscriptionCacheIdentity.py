import pytest
from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.transcription.cache.identity import (
    TranscriptionCacheIdentity,
)


def test__transcription_cache_identity__has_nominal_identity_role() -> None:
    assert issubclass(TranscriptionCacheIdentity, AbstractIdentity)
    with pytest.raises(ValueError, match="unsupported"):
        TranscriptionCacheIdentity(
            cache_key="forged",
            input_id="input",
            processor_name="processor",
            processor_version="1",
            configuration_identity=(),
            contract_version="unsupported",
        )
