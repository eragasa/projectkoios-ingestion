from __future__ import annotations

import inspect

from projectkoios.ingestion.storage.extraction.base import (
    AbstractExtractionPublicationStore,
)


def test__abstract_extraction_publication_store__is_abstract() -> None:
    assert inspect.isabstract(AbstractExtractionPublicationStore)
