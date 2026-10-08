"""Typed pytest injection for reading-evidence foundation tests."""

import pytest

from .fixture import ReadingEvidenceFoundationFixture


@pytest.fixture
def reading_evidence_fixture() -> ReadingEvidenceFoundationFixture:
    """Return one immutable reading-evidence fixture owner."""
    return ReadingEvidenceFoundationFixture()
