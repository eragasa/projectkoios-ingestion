"""Typed pytest injection for current reading producer actions."""

import pytest

from tests.projectkoios.ingestion.transcript.reading.evidence.production.fixture import (  # noqa: E501
    ReadingCurrentProducerFixture,
)


@pytest.fixture(scope="module")
def reading_current_producer_fixture() -> ReadingCurrentProducerFixture:
    """Provide one exact current reading producer fixture."""
    return ReadingCurrentProducerFixture.build()
