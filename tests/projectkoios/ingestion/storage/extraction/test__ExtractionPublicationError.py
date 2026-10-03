from projectkoios.ingestion.storage.extraction.error import (
    ExtractionPublicationError,
)


def test__extraction_publication_error__is_runtime_failure() -> None:
    error = ExtractionPublicationError("bounded publication failure")

    assert isinstance(error, RuntimeError)
