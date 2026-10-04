from projectkoios.ingestion.base import AbstractIdentity
from projectkoios.ingestion.transcription.cache.identity import (
    TranscriptionCacheIdentity,
)


def test__transcription_cache_identity__has_nominal_identity_role() -> None:
    assert issubclass(TranscriptionCacheIdentity, AbstractIdentity)
