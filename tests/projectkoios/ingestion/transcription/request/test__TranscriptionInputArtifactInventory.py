from projectkoios.ingestion.base import AbstractDerivation
from projectkoios.ingestion.transcription.request.artifact_inventory import (
    TranscriptionInputArtifactInventory,
)


def test__transcriptioninputartifactinventory__has_nominal_domain_role() -> (
    None
):
    assert issubclass(TranscriptionInputArtifactInventory, AbstractDerivation)
